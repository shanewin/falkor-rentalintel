from django.conf import settings
import cloudinary

def cloudinary_config(request):
    """
    Add Cloudinary configuration to template context
    """
    return {
        'CLOUDINARY_CLOUD_NAME': cloudinary.config().cloud_name,
        'CLOUDINARY_API_KEY': cloudinary.config().api_key,
        'CLOUDINARY_UPLOAD_PRESET': 'unsigned_cards',  # Use the whitelisted unsigned preset
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'Falkor'),
    }