import json
from django import template

register = template.Library()

@register.filter
def json_loads(value):
    """Converts a JSON string into a Python dictionary inside Django templates."""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return {}  # Return an empty dictionary if the JSON is invalid
