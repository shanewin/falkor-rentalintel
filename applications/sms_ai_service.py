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


def generate_reminder_sms(application, missing_fields):
    """
    Use Claude to generate a friendly, concise SMS reminding the applicant
    about their missing fields.

    Args:
        application: Application model instance
        missing_fields: list of dicts [{'field': 'employer', 'label': 'Employer Name', ...}, ...]

    Returns:
        str: SMS message text (under 320 chars)
    """
    applicant_name = "there"
    personal_info = getattr(application, 'personal_info', None)
    if personal_info and personal_info.first_name:
        applicant_name = personal_info.first_name

    building = application.get_building_display()
    field_labels = [f['label'] for f in missing_fields[:8]]

    prompt = f"""Generate a SHORT, friendly SMS reminder for a rental application. 
Keep it under 280 characters so there's room for the sign-off.

Applicant's first name: {applicant_name}
Property: {building}
Missing fields: {', '.join(field_labels)}

Rules:
- Be warm and professional
- List the 3-4 most important missing items by name
- If there are more than 4 missing fields, say "and a few more details"
- End by saying they can reply to this text with the info
- Do NOT include any greeting like "Dear" — just use their first name casually
- Do NOT include any signature or phone number
- Output ONLY the message text, nothing else"""

    system = "You are a concise SMS writer for a rental application platform called Falkor. Write short, friendly texts."
    text = _call_claude(prompt, system_prompt=system, max_tokens=150, temperature=0.7)

    if text:
        text = text.strip().strip('"').strip("'")
        return text[:320]

    return _fallback_reminder(application, missing_fields)


def _fallback_reminder(application, missing_fields):
    """Fallback if Claude is unavailable — simple template-based message."""
    personal_info = getattr(application, 'personal_info', None)
    name = personal_info.first_name if personal_info and personal_info.first_name else "there"
    labels = [f['label'] for f in missing_fields[:4]]
    items = ", ".join(labels)
    extra = f" and {len(missing_fields) - 4} more" if len(missing_fields) > 4 else ""
    return f"Hi {name}! Your rental application is almost complete. We still need: {items}{extra}. You can reply to this text with that info, or log in at rentfalkor.com."


def parse_applicant_reply(conversation, reply_text):
    """
    Use Claude to extract field values from an applicant's SMS reply.

    Args:
        conversation: SMSConversation instance
        reply_text: The applicant's reply text

    Returns:
        dict with 'extracted', 'still_missing', and 'reply' keys
    """
    pending = conversation.pending_fields

    field_descriptions = []
    for f in pending:
        desc = f"- {f['field']} ({f['label']}, type: {f['type']})"
        field_descriptions.append(desc)

    history_text = ""
    for msg in conversation.messages[-6:]:
        role = "Assistant" if msg['role'] == 'assistant' else "Applicant"
        history_text += f"{role}: {msg['content']}\n"

    prompt = f"""You are parsing an SMS reply from a rental applicant. Extract any field values they provided.

FIELDS WE NEED (still missing):
{chr(10).join(field_descriptions)}

CONVERSATION HISTORY:
{history_text}
Applicant: {reply_text}

INSTRUCTIONS:
1. Extract any field values the applicant provided in their message
2. For dates, convert to YYYY-MM-DD format
3. For booleans (yes/no questions), convert to true/false
4. For decimals/money, extract just the number (no $ sign)
5. For integers, extract just the number
6. Only extract fields that are in the FIELDS WE NEED list above
7. If the applicant's message doesn't contain useful field data, return empty extracted
8. Generate a SHORT follow-up SMS (under 200 chars) that:
   - Acknowledges what was received (if anything)
   - Asks about remaining missing fields (pick 2-3 most important)
   - If all fields are now covered, thank them and say the application is updated
9. If the applicant seems confused or asks a question, answer helpfully and re-ask for the fields

Return valid JSON only:
{{
  "extracted": {{"field_name": "value", ...}},
  "still_missing_fields": ["field_name1", "field_name2"],
  "reply": "Your follow-up SMS text here"
}}"""

    system = "You are a rental application assistant. Parse applicant SMS replies and extract structured data. Always respond with valid JSON only."
    text = _call_claude(prompt, system_prompt=system, max_tokens=300, temperature=0.3)

    if text:
        try:
            # Extract JSON from response (Claude may wrap it in text)
            import re
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(text)

            # Map still_missing_fields back to full field dicts
            still_missing_names = set(result.get('still_missing_fields', []))
            still_missing = [f for f in pending if f['field'] in still_missing_names]

            # If AI forgot to list remaining fields, compute them ourselves
            extracted_keys = set(result.get('extracted', {}).keys())
            if not still_missing:
                still_missing = [f for f in pending if f['field'] not in extracted_keys]

            return {
                'extracted': result.get('extracted', {}),
                'still_missing': still_missing,
                'reply': result.get('reply', '').strip('"')[:320],
            }
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Failed to parse Claude response: {e}")

    return _fallback_parse(pending, reply_text)


def _fallback_parse(pending, reply_text):
    """Fallback if Claude is unavailable — no extraction, just ask again."""
    labels = [f['label'] for f in pending[:3]]
    return {
        'extracted': {},
        'still_missing': pending,
        'reply': f"Thanks for your reply! We still need: {', '.join(labels)}. Could you provide those details?",
    }


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


def save_extracted_fields(conversation, extracted):
    """
    Save extracted field values to the appropriate model.
    """
    from .sms_conversation import SMS_SAFE_FIELDS

    application = conversation.application
    saved = []

    field_lookup = {}
    for req in conversation.requested_fields:
        field_lookup[req['field']] = (req['model'], req.get('type', 'str'))

    for field_name, raw_value in extracted.items():
        if field_name not in field_lookup:
            logger.warning(f"Extracted field '{field_name}' not in requested fields — skipping")
            continue

        model_name, field_type = field_lookup[field_name]

        # Security check: ensure this field is in the whitelist
        if model_name not in SMS_SAFE_FIELDS or field_name not in SMS_SAFE_FIELDS[model_name]:
            logger.warning(f"Field '{field_name}' not in SMS_SAFE_FIELDS whitelist — skipping")
            continue

        model_instance = getattr(application, model_name, None)
        if not model_instance:
            logger.warning(f"Application {application.id} has no {model_name} — skipping")
            continue

        coerced = coerce_value(raw_value, field_type)
        if coerced is not None:
            setattr(model_instance, field_name, coerced)
            try:
                model_instance.save(update_fields=[field_name, 'updated_at'])
                conversation.mark_field_collected(field_name, raw_value)
                saved.append(field_name)
                logger.info(f"SMS collected: {field_name}={coerced} for App #{application.id}")
            except Exception as e:
                logger.error(f"Failed to save {field_name} for App #{application.id}: {e}")

    return saved


def handle_inbound_reply(conversation, reply_text):
    """
    Main handler for inbound SMS replies in an active conversation.
    Called from the Telnyx webhook when a message.received event matches
    an active SMSConversation.
    """
    from .sms_utils import SMSBackend

    # Record the applicant's message
    conversation.add_message('user', reply_text)

    # Parse the reply with Claude
    result = parse_applicant_reply(conversation, reply_text)
    extracted = result.get('extracted', {})
    still_missing = result.get('still_missing', [])
    follow_up = result.get('reply', '')

    # Save any extracted fields to the database
    saved = []
    if extracted:
        saved = save_extracted_fields(conversation, extracted)

    # Log activity
    if saved:
        try:
            from .models import ApplicationActivity
            ApplicationActivity.objects.create(
                application=conversation.application,
                description=f"SMS collected {len(saved)} field(s): {', '.join(saved)}"
            )
        except Exception:
            pass

    # Determine if we're done
    if not still_missing or not conversation.pending_fields:
        if not follow_up:
            follow_up = "All set! We've updated your application with the info you provided. Thank you!"
        conversation.add_message('assistant', follow_up)
        conversation.complete()
    else:
        if not follow_up:
            labels = [f['label'] for f in still_missing[:3]]
            follow_up = f"Thanks! We still need: {', '.join(labels)}. Can you provide those?"
        conversation.add_message('assistant', follow_up)

    # Send the follow-up/confirmation SMS via Telnyx
    if follow_up:
        try:
            sms = SMSBackend()
            sms.send_sms(conversation.phone_number, follow_up)
        except Exception as e:
            logger.error(f"Failed to send follow-up SMS: {e}")
