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
