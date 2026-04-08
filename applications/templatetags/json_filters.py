import json
import re
from django import template

register = template.Library()

@register.filter
def json_loads(value):
    """Converts a JSON string into a Python dictionary inside Django templates."""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}  # Return an empty dictionary if the JSON is invalid

@register.filter
def format_phone(value):
    """Formats a raw phone number string into (xxx) xxx-xxxx."""
    if not value:
        return value
    digits = re.sub(r'\D', '', str(value))
    if len(digits) == 11 and digits[0] == '1':
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return value  # Return as-is if it doesn't look like a standard US number
