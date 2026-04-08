import json
import logging
import os
import requests
from datetime import datetime
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

# Anthropic API config — matches existing pattern in doc_analysis/secure_api_client.py
ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'
ANTHROPIC_MODEL = 'claude-3-haiku-20240307'


def _call_claude(prompt, system_prompt="", max_tokens=300, temperature=0.3):
    """
    Call Anthropic Claude API using the same pattern as secure_api_client.py.
    Returns the response text, or None on failure.
    """
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        logger.error("ANTHROPIC_API_KEY not configured")
        return None

    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
    }

    payload = {
        'model': ANTHROPIC_MODEL,
        'max_tokens': max_tokens,
        'temperature': temperature,
        'messages': [{'role': 'user', 'content': prompt}],
    }

    if system_prompt:
        payload['system'] = system_prompt

    try:
        response = requests.post(
            ANTHROPIC_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        return result['content'][0]['text']
    except Exception as e:
        logger.error(f"Anthropic API call failed: {e}")
        return None


# ──────────────────────────────────────────────────────────────────
# STEP 1: Generate the opening SMS (asks about the FIRST field)
# ──────────────────────────────────────────────────────────────────

def generate_reminder_sms(application, missing_fields):
    """
    Generate a friendly opening SMS that introduces the conversation
    and asks about the FIRST missing field only.

    This message is shown to the broker in the modal for review before sending.
    """
    applicant_name = "there"
    personal_info = getattr(application, 'personal_info', None)
    if personal_info and personal_info.first_name:
        applicant_name = personal_info.first_name

    building = application.get_building_display()
    first_field = missing_fields[0]
    total = len(missing_fields)

    prompt = f"""Generate a SHORT, friendly SMS to start a conversation with a rental applicant.
You need to collect {total} piece(s) of missing info, ONE AT A TIME via text.

This first message should:
1. Greet {applicant_name} by name (casual, no "Dear")
2. Briefly mention this is about their Falkor rental application for {building}
3. Say you have {total} quick question(s) to help complete their app
4. Ask the FIRST question: "{first_field['label']}"
5. Make the question feel natural and conversational

Keep it under 280 characters total.
Output ONLY the message text, nothing else."""

    system = "You are a concise SMS writer for a rental application platform called Falkor. Write short, friendly texts. One question at a time."
    text = _call_claude(prompt, system_prompt=system, max_tokens=150, temperature=0.7)

    if text:
        text = text.strip().strip('"').strip("'")
        return text[:320]

    return _fallback_opening(applicant_name, building, first_field, total)


def _fallback_opening(name, building, first_field, total_fields):
    """Fallback if Claude is unavailable — simple template for the opening message."""
    return (
        f"Hi {name}! Just a few quick questions to finish your Falkor "
        f"application for {building} ({total_fields} total). "
        f"First up: What is your {first_field['label']}?"
    )[:320]


# ──────────────────────────────────────────────────────────────────
# STEP 2: Parse a single-field reply from the applicant
# ──────────────────────────────────────────────────────────────────

def parse_single_field_reply(conversation, reply_text):
    """
    Parse the applicant's reply for the ONE field we're currently asking about.

    Returns dict:
        {
            'value': <extracted value or None>,
            'needs_retry': bool,      # True if we couldn't extract a usable value
            'follow_up': str,         # Next SMS to send
        }
    """
    current = conversation.current_field
    if not current:
        return {
            'value': None,
            'needs_retry': False,
            'follow_up': "All set! Your application has been updated. Thank you!",
        }

    next_field = conversation.next_field
    fields_remaining = conversation.fields_remaining

    applicant_name = "there"
    personal_info = getattr(conversation.application, 'personal_info', None)
    if personal_info and personal_info.first_name:
        applicant_name = personal_info.first_name

    # Special handling for skip-like replies
    skip_words = {'skip', 'n/a', 'na', 'none', 'pass', 'no', '-', 'idk', "don't know", "dont know"}
    if reply_text.strip().lower() in skip_words:
        # For optional-feeling fields, allow skipping
        if next_field:
            follow_up = _build_next_question(applicant_name, next_field, fields_remaining - 1)
        else:
            follow_up = f"All done! Thanks for completing your application, {applicant_name}!"

        return {
            'value': None,
            'needs_retry': False,  # Not a retry — they chose to skip
            'follow_up': follow_up,
        }

    prompt = f"""An applicant replied to a question about their rental application.

THE QUESTION WAS ABOUT: {current['label']} (field type: {current['type']})

THEIR REPLY: "{reply_text}"

INSTRUCTIONS:
1. Extract the value for "{current['label']}" from their reply
2. For dates, convert to YYYY-MM-DD format
3. For booleans (Yes/No questions), convert to "true" or "false"
4. For decimals/money, extract just the number (no $ sign)
5. If their reply is a valid answer to the question, extract it
6. If their reply does NOT answer the question (gibberish, unrelated, or too vague), set value to null

Return valid JSON only:
{{
  "value": "extracted value here or null",
  "understood": true/false
}}"""

    system = "You are a data extraction assistant. Parse the applicant's SMS reply for a single field. Return JSON only."
    text = _call_claude(prompt, system_prompt=system, max_tokens=100, temperature=0.1)

    extracted_value = None
    understood = False

    if text:
        try:
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(text)

            raw_value = result.get('value')
            understood = result.get('understood', False)

            if raw_value is not None and str(raw_value).lower() not in ('null', 'none', ''):
                extracted_value = str(raw_value)

        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to parse Claude response: {e}")
            # Fallback: if the reply is short and looks like a direct answer, use it as-is
            extracted_value = _naive_extract(reply_text, current)

    else:
        # Claude unavailable — naive extraction
        extracted_value = _naive_extract(reply_text, current)

    # Build the follow-up message
    if extracted_value:
        # Success — acknowledge and move to next
        if next_field:
            follow_up = _build_next_question(applicant_name, next_field, fields_remaining - 1, ack=True)
        else:
            follow_up = f"Got it! That's everything — your application is all updated. Thank you, {applicant_name}! 🎉"

        return {
            'value': extracted_value,
            'needs_retry': False,
            'follow_up': follow_up,
        }
    else:
        # Couldn't extract — ask again
        retry_msg = _build_retry(applicant_name, current)
        return {
            'value': None,
            'needs_retry': True,
            'follow_up': retry_msg,
        }


def _naive_extract(reply_text, field):
    """Fallback extraction when Claude is unavailable — accepts the raw reply for simple types."""
    text = reply_text.strip()
    if not text or len(text) > 200:
        return None

    if field['type'] == 'str':
        return text
    elif field['type'] == 'bool':
        lower = text.lower()
        if lower in ('yes', 'y', 'yeah', 'yep', 'true', '1'):
            return 'true'
        elif lower in ('no', 'n', 'nah', 'nope', 'false', '0'):
            return 'false'
        return None
    elif field['type'] in ('int', 'decimal'):
        cleaned = ''.join(c for c in text if c.isdigit() or c == '.')
        return cleaned if cleaned else None
    else:
        return text


def _build_next_question(name, next_field, remaining, ack=False):
    """Build a follow-up SMS asking about the next field."""
    ack_prefix = "Got it! " if ack else ""
    remaining_text = f" ({remaining} left)" if remaining > 1 else " (last one!)"
    label = next_field['label']

    # Make certain questions more natural
    question = _humanize_question(label, next_field.get('type', 'str'))

    return f"{ack_prefix}{question}{remaining_text}"[:320]


def _build_retry(name, field):
    """Build a clarification message when we couldn't understand the reply."""
    label = field['label']
    ftype = field.get('type', 'str')

    if ftype == 'date':
        return f"Sorry, I didn't catch that. Could you provide your {label} as a date? (e.g., 01/15/2025)"[:320]
    elif ftype == 'decimal':
        return f"Could you provide your {label} as a number? (e.g., 75000)"[:320]
    elif ftype == 'bool':
        return f"Just to confirm — {label}? (Yes or No)"[:320]
    elif ftype == 'int':
        return f"Could you provide your {label} as a number?"[:320]
    else:
        return f"Sorry, I didn't catch that. What is your {label}?"[:320]


def _humanize_question(label, ftype):
    """Convert a field label into a natural-sounding SMS question."""
    label_lower = label.lower()

    # Special phrasings for certain fields
    if 'middle name' in label_lower:
        return "Do you have a middle name? If so, what is it?"
    elif 'suffix' in label_lower:
        return "Do you have a name suffix? (Jr., Sr., III, etc.)"
    elif 'pets' in label_lower:
        return "Do you have any pets? (Yes/No)"
    elif 'currently employed' in label_lower:
        return "Are you currently employed? (Yes/No)"
    elif 'move-in date' in label_lower or 'move in' in label_lower:
        return "When is your desired move-in date?"
    elif 'reason for moving' in label_lower:
        return "What's your reason for moving?"
    elif 'how did you hear' in label_lower or 'referral' in label_lower:
        return "How did you hear about us?"
    elif 'annual income' in label_lower:
        return "What is your annual income?"
    elif 'how long' in label_lower:
        return "How long have you been at your current job?"
    elif ftype == 'bool':
        return f"{label}? (Yes or No)"
    elif ftype == 'date':
        return f"What is your {label}? (e.g., 01/15/2025)"
    else:
        return f"What is your {label}?"


# ──────────────────────────────────────────────────────────────────
# Type coercion (unchanged from original)
# ──────────────────────────────────────────────────────────────────

def coerce_value(value, field_type):
    """
    Convert a string value to the appropriate Python type for saving to the model.
    """
    if value is None or (isinstance(value, str) and not value.strip()):
        return None

    try:
        if field_type == 'str':
            return str(value).strip()

        elif field_type == 'int':
            cleaned = ''.join(c for c in str(value) if c.isdigit())
            return int(cleaned) if cleaned else None

        elif field_type == 'decimal':
            cleaned = str(value).replace('$', '').replace(',', '').strip()
            return Decimal(cleaned)

        elif field_type == 'date':
            date_str = str(value).strip()
            for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%m-%d-%Y', '%B %d, %Y', '%b %d, %Y', '%m/%d/%y'):
                try:
                    return datetime.strptime(date_str, fmt).date()
                except ValueError:
                    continue
            logger.warning(f"Could not parse date: {value}")
            return None

        elif field_type == 'bool':
            val = str(value).lower().strip()
            if val in ('true', 'yes', 'y', '1', 'yeah', 'yep'):
                return True
            elif val in ('false', 'no', 'n', '0', 'nah', 'nope'):
                return False
            return None

        else:
            return str(value)

    except (ValueError, InvalidOperation, TypeError) as e:
        logger.warning(f"Failed to coerce '{value}' to {field_type}: {e}")
        return None


# ──────────────────────────────────────────────────────────────────
# Save a SINGLE extracted field
# ──────────────────────────────────────────────────────────────────

def save_single_field(conversation, field, raw_value):
    """
    Save one extracted field value to the appropriate model.
    Returns True if saved successfully, False otherwise.
    """
    from .sms_conversation import SMS_SAFE_FIELDS

    application = conversation.application
    model_name = field['model']
    field_name = field['field']
    field_type = field.get('type', 'str')

    # Security check: whitelist only
    if model_name not in SMS_SAFE_FIELDS or field_name not in SMS_SAFE_FIELDS[model_name]:
        logger.warning(f"Field '{field_name}' not in SMS_SAFE_FIELDS whitelist — skipping")
        return False

    model_instance = getattr(application, model_name, None)
    if not model_instance:
        logger.warning(f"Application {application.id} has no {model_name} — skipping")
        return False

    coerced = coerce_value(raw_value, field_type)
    if coerced is None:
        logger.warning(f"Coercion failed for {field_name}={raw_value} (type={field_type})")
        return False

    setattr(model_instance, field_name, coerced)
    try:
        model_instance.save(update_fields=[field_name, 'updated_at'])
        conversation.mark_field_collected(field_name, raw_value)
        logger.info(f"SMS collected: {field_name}={coerced} for App #{application.id}")
        return True
    except Exception as e:
        logger.error(f"Failed to save {field_name} for App #{application.id}: {e}")
        return False


# ──────────────────────────────────────────────────────────────────
# MAIN HANDLER: process each inbound reply (one field at a time)
# ──────────────────────────────────────────────────────────────────

def handle_inbound_reply(conversation, reply_text):
    """
    Main handler for inbound SMS replies in an active conversation.
    Processes ONE field at a time:
      1. Parse the reply for the current field
      2. If valid, save it and advance to the next field
      3. If invalid, ask again
      4. If all fields done, mark conversation complete
      5. Send the follow-up SMS
    """
    from .sms_utils import SMSBackend

    # Record the applicant's message
    conversation.add_message('user', reply_text)

    current = conversation.current_field
    if not current:
        # All fields already collected — shouldn't normally happen
        follow_up = "Your application is already complete. Thank you!"
        conversation.add_message('assistant', follow_up)
        conversation.complete()
        _send_sms(conversation.phone_number, follow_up)
        return

    # Parse the reply for this single field
    result = parse_single_field_reply(conversation, reply_text)
    value = result.get('value')
    needs_retry = result.get('needs_retry', False)
    follow_up = result.get('follow_up', '')

    saved = False
    if value and not needs_retry:
        # Try to save the extracted value
        saved = save_single_field(conversation, current, value)

        if not saved:
            # Coercion/save failed — ask again with a type hint
            follow_up = _build_retry(
                _get_applicant_name(conversation),
                current
            )
            needs_retry = True

    if saved:
        # Success — advance to next field
        conversation.advance_field()

        # Log activity
        try:
            from .models import ApplicationActivity
            ApplicationActivity.objects.create(
                application=conversation.application,
                description=f"SMS collected: {current['label']} = \"{value}\""
            )
        except Exception:
            pass

        # Check if all done
        if not conversation.current_field:
            follow_up = f"All done! Your application is fully updated. Thank you! 🎉"
            conversation.add_message('assistant', follow_up)
            conversation.complete()

            try:
                from .models import ApplicationActivity
                ApplicationActivity.objects.create(
                    application=conversation.application,
                    description=f"SMS conversation completed — {len(conversation.collected_fields)} fields collected"
                )
            except Exception:
                pass
        else:
            conversation.add_message('assistant', follow_up)
    elif not needs_retry:
        # Skipped field — advance without saving
        conversation.advance_field()

        if not conversation.current_field:
            follow_up = f"All done! Your application has been updated. Thank you! 🎉"
            conversation.add_message('assistant', follow_up)
            conversation.complete()
        else:
            conversation.add_message('assistant', follow_up)
    else:
        # Retry — don't advance, ask again
        conversation.add_message('assistant', follow_up)

    # Send the follow-up SMS
    if follow_up:
        _send_sms(conversation.phone_number, follow_up)


def _send_sms(phone_number, message):
    """Helper to send an SMS, handling errors gracefully."""
    try:
        from .sms_utils import SMSBackend
        sms = SMSBackend()
        sms.send_sms(phone_number, message)
    except Exception as e:
        logger.error(f"Failed to send follow-up SMS to {phone_number}: {e}")


def _get_applicant_name(conversation):
    """Get the applicant's first name from the conversation's application."""
    personal_info = getattr(conversation.application, 'personal_info', None)
    if personal_info and personal_info.first_name:
        return personal_info.first_name
    return "there"


# ──────────────────────────────────────────────────────────────────
# Legacy compat: keep old function names so callers don't break
# ──────────────────────────────────────────────────────────────────

def save_extracted_fields(conversation, extracted):
    """Legacy wrapper — no longer used in the new one-at-a-time flow."""
    saved = []
    for field_name, raw_value in extracted.items():
        for req in conversation.requested_fields:
            if req['field'] == field_name:
                if save_single_field(conversation, req, raw_value):
                    saved.append(field_name)
                break
    return saved


def parse_applicant_reply(conversation, reply_text):
    """Legacy wrapper — redirects to single-field parsing."""
    result = parse_single_field_reply(conversation, reply_text)
    extracted = {}
    current = conversation.current_field
    if current and result.get('value'):
        extracted[current['field']] = result['value']
    return {
        'extracted': extracted,
        'still_missing': conversation.pending_fields,
        'reply': result.get('follow_up', ''),
    }
