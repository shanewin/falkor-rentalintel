from django import template
import random

register = template.Library()

@register.filter
def get_fallback_image(apartment_id):
    """
    Returns a deterministic placeholder image URL.
    Using Placehold.co as it is extremely reliable and fast compared to Unsplash.
    """
    # Use ID to pick a color or style if we wanted, but for now just reliability.
    safe_id = apartment_id if apartment_id else 0
    
    # We can stick to Unsplash for the 'nice' ones that work, but one of them was bad.
    # Let's use a very reliable list of Unsplash IDs that we verified, 
    # OR just use the one that we saw working in your screenshot (Mcmillan Tower).
    
    # The working image from your screenshot looked like a nice living room. 
    # Let's use that specific one + a few high-reliability architecture shots.
    images = [
        'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=600&h=400&fit=crop&q=80', # Working (Mcmillan style)
        'https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600&h=400&fit=crop&q=80', # Modern
        'https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=600&h=400&fit=crop&q=80', # Luxury
        'https://images.unsplash.com/photo-1560185007-cde436f6a4d0?w=600&h=400&fit=crop&q=80', # Wide living room
    ]
    
    
    return images[safe_id % len(images)]

@register.filter
def format_phone(value):
    """
    Formats a phone number as (XXX) XXX-XXXX.
    Expects a 10-digit number or string.
    """
    if not value:
        return ""
    
    # Strip non-digits
    import re
    digits = re.sub(r'\D', '', str(value))
    
    # Handle standard US numbers without country code
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    
    # Handle US numbers with country code '1'
    elif len(digits) == 11 and digits.startswith('1'):
        return f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}"
    
    # Handle numbers with extensions (assuming >10 digits and probably US-ish start)
    # This is a best-effort heuristic for the messy data seen (+1-971...x5555)
    elif len(digits) > 10:
        # If it looks like US (starts with 1), try to format the first 11 digits
        if digits.startswith('1'):
             main_number = f"({digits[1:4]}) {digits[4:7]}-{digits[7:11]}"
             extension = digits[11:]
             return f"{main_number} x{extension}"
        else:
             # Assume first 10 is the number, rest is extension
             main_number = f"({digits[:3]}) {digits[3:6]}-{digits[6:10]}"
             extension = digits[10:]
             return f"{main_number} x{extension}"
             
    return value
