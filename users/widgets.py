from django import forms
from django.utils.safestring import mark_safe
from cloudinary.forms import CloudinaryFileField
import json


class CloudinaryPhotoUploadWidget(forms.ClearableFileInput):
    """
    Enhanced photo upload widget with preview and Cloudinary integration
    """
    template_name = 'users/widgets/photo_upload.html'
    
    class Media:
        css = {
            'all': ('users/css/photo-upload.css',)
        }
        js = (
            'https://upload-widget.cloudinary.com/global/all.js',
            'users/js/photo-upload.js',
        )
    
    def __init__(self, attrs=None, options=None):
        self.options = options or {}
        # Default Cloudinary upload options
        self.default_options = {
            'cropping': True,
            'croppingAspectRatio': 1,
            'croppingDefaultSelectionRatio': 0.9,
            'croppingShowDimensions': True,
            'croppingCoordinatesMode': 'custom',
            'folder': 'profile_photos',
            'allowedFormats': ['jpg', 'jpeg', 'png', 'gif', 'webp'],
            'maxFileSize': 10485760,  # 10MB
            'clientAllowedFormats': ['jpg', 'jpeg', 'png', 'gif', 'webp'],
            'resourceType': 'image',
            'multiple': False,
            'showSkipCropButton': False,
            'styles': {
                'palette': {
                    'window': '#FFFFFF',
                    'windowBorder': '#90A0B3',
                    'tabIcon': '#ffcc00',
                    'menuIcons': '#5A616A',
                    'textDark': '#000000',
                    'textLight': '#FFFFFF',
                    'link': '#ffcc00',
                    'action': '#ffcc00',
                    'inactiveTabIcon': '#0E2F5A',
                    'error': '#F44235',
                    'inProgress': '#ffcc00',
                    'complete': '#20B832',
                    'sourceBg': '#E4EBF1'
                },
                'fonts': {
                    'default': {
                        'active': True
                    }
                }
            }
        }
        self.default_options.update(self.options)
        super().__init__(attrs)
    
    def render(self, name, value, attrs=None, renderer=None):
        """Custom render method for the widget"""
        attrs = attrs or {}
        attrs['data-cloudinary-options'] = json.dumps(self.default_options)
        attrs['data-field-name'] = name
        
        # Get current photo URL if value exists
        current_photo_url = None
        current_public_id = None
        if value and hasattr(value, 'url'):
            current_photo_url = value.url
            if hasattr(value, 'public_id'):
                current_public_id = value.public_id
        
        attrs['data-current-photo'] = current_photo_url or ''
        attrs['data-current-public-id'] = current_public_id or ''
        
        return super().render(name, value, attrs, renderer)


class CloudinaryDirectUploadWidget(forms.HiddenInput):
    """
    Widget for direct Cloudinary uploads using the Upload Widget
    """
    template_name = 'users/widgets/cloudinary_direct_upload.html'
    
    class Media:
        css = {
            'all': ('users/css/photo-upload.css',)
        }
        js = (
            'https://upload-widget.cloudinary.com/global/all.js',
            'users/js/cloudinary-upload.js',
        )
    
    def __init__(self, attrs=None, options=None):
        self.options = options or {}
        super().__init__(attrs)
    
    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs['class'] = attrs.get('class', '') + ' cloudinary-upload-field'
        attrs['data_cloudinary_options'] = json.dumps(self.options)
        
        # Handle existing photo - use underscores for template compatibility
        photo_url = ''
        public_id = ''
        if value:
            if hasattr(value, 'url'):
                photo_url = value.url
            if hasattr(value, 'public_id'):
                public_id = value.public_id
        
        attrs['data_current_photo'] = photo_url
        attrs['data_public_id'] = public_id
        
        return super().render(name, value, attrs, renderer)