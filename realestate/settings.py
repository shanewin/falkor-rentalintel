import os
from decouple import config

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config('SECRET_KEY')

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'web', '0.0.0.0', '.railway.app', '.up.railway.app']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',  # Required for Sites framework
    'django.contrib.humanize',  # For number formatting in templates
    'applications',
    'buildings',
    'applicants',
    'apartments',
    'cloudinary',
    'cloudinary_storage',
    'crispy_forms',
    'crispy_bootstrap5',
    'ckeditor',
    'users',
    'doc_analysis',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
]

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

# CKEditor Configuration
CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': [
            ['Bold', 'Italic', 'Underline'],
            ['FontSize'],
            ['TextColor', 'BGColor'],
            ['NumberedList', 'BulletedList'],
            ['Table'],
            ['Link', 'Unlink'],
            ['RemoveFormat']
        ],
        'height': 200,
        'width': '100%',
        'toolbarCanCollapse': False,
        'forcePasteAsPlainText': False,
        'removePlugins': 'exportpdf',
        'colorButton_colors': 'ffcc00,000000,ffffff,6c757d,28a745,dc3545,17a2b8,ffc107',
        'colorButton_enableMore': False,
        'fontSize_sizes': '12/12px;14/14px;16/16px;18/18px;20/20px;24/24px;28/28px'
    }
}

# Sites framework
SITE_ID = 1

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Activity tracking middleware - must be after AuthenticationMiddleware
    # Activity tracking middleware - must be after AuthenticationMiddleware
    'applicants.middleware.ActivityTrackingMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'realestate.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'users.context_processors.cloudinary_config',
            ],
        },
    },
]

WSGI_APPLICATION = 'realestate.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DATABASE_NAME', 'doorway_db'),
        'USER': os.getenv('DATABASE_USER', 'doorway_user'),
        'PASSWORD': os.getenv('DATABASE_PASSWORD', 'doorway_pass'),
        'HOST': os.getenv('DATABASE_HOST', 'db'),
        'PORT': os.getenv('DATABASE_PORT', '5432'),
    }
}

from django.db.backends.signals import connection_created
from django.dispatch import receiver

@receiver(connection_created)
def enable_vector_extension(sender, connection, **kwargs):
    """Ensure the 'vector' extension is enabled only if not already created."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM pg_extension WHERE extname='vector';")
        if not cursor.fetchone():  # If 'vector' extension does not exist
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")


AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': config('GOOGLE_CLIENT_ID', default=''),
            'secret': config('GOOGLE_CLIENT_SECRET', default=''),
            'key': ''
        },
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'America/New_York'

USE_I18N = True

USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

import cloudinary
import cloudinary.uploader
import cloudinary.api	

cloudinary.config(
    cloud_name=config('CLOUDINARY_CLOUD_NAME'),
    api_key=config('CLOUDINARY_API_KEY'),
    api_secret=config('CLOUDINARY_API_SECRET'),
)

STATIC_URL = '/static/'

STATIC_ROOT = BASE_DIR / 'static_root'

STATICFILES_DIRS = [
    BASE_DIR / 'staticfiles',  # ensure collected assets are served in dev
    BASE_DIR / 'static',       # Global static assets (css/doorway-theme.css)
    BASE_DIR / 'apartments/static/apartments',
    BASE_DIR / 'applicants/static/applicants',
    BASE_DIR / 'buildings/static/buildings',
    BASE_DIR / 'applications/static/applications',
    BASE_DIR / 'users/static/users',
]


if DEBUG:
    STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage' 
else:
    STATICFILES_STORAGE = 'cloudinary_storage.storage.StaticHashedCloudinaryStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Cloudinary media storage
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

AUTH_USER_MODEL = 'users.User'

# Authentication settings
LOGIN_URL = '/users/login/'
LOGIN_REDIRECT_URL = '/'  # Will be handled by redirect_by_role function
LOGOUT_REDIRECT_URL = '/users/login/'

# Session settings
SESSION_COOKIE_AGE = 86400 * 7  # 1 week
SESSION_SAVE_EVERY_REQUEST = True

# Field Encryption Settings
FIELD_ENCRYPTION_KEY = config('FIELD_ENCRYPTION_KEY')

# Professional Email Configuration
EMAIL_SERVICE = config('EMAIL_SERVICE', default='console')

# SendGrid Configuration
SENDGRID_API_KEY = config('SENDGRID_API_KEY', default='')
SENDGRID_FROM_EMAIL = config('SENDGRID_FROM_EMAIL', default='')

# Mailgun Configuration  
MAILGUN_API_KEY = config('MAILGUN_API_KEY', default='')
MAILGUN_DOMAIN = config('MAILGUN_DOMAIN', default='')

# Amazon SES Configuration
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
AWS_SES_REGION = config('AWS_SES_REGION', default='us-east-1')
AWS_SES_FROM_EMAIL = config('AWS_SES_FROM_EMAIL', default='')

# General Email Settings
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='DoorWay <noreply@doorway.com>')
SITE_NAME = config('SITE_NAME', default='DoorWay')
REPLY_TO_EMAIL = config('REPLY_TO_EMAIL', default='support@doorway.com')

# Auto-select email backend based on service configuration
def get_email_backend():
    """Select appropriate email backend based on configuration"""
    service = EMAIL_SERVICE.lower()
    
    if service == 'sendgrid' and SENDGRID_API_KEY:
        return 'applications.email_backends.SendGridBackend'
    elif service == 'mailgun' and MAILGUN_API_KEY:
        return 'applications.email_backends.MailgunBackend'
    elif service == 'ses' and AWS_ACCESS_KEY_ID:
        return 'applications.email_backends.AmazonSESBackend'
    else:
        # Default to console for development/testing
        return 'django.core.mail.backends.console.EmailBackend'

EMAIL_BACKEND = get_email_backend()

# Twilio SMS Configuration
TWILIO_ACCOUNT_SID = config('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = config('TWILIO_AUTH_TOKEN', default='')
TWILIO_FROM_PHONE = config('TWILIO_FROM_PHONE', default='')

# Site URL for generating links in emails/SMS
SITE_URL = config('SITE_URL', default='http://localhost:8000')

# Mapbox (for map-based apartment search)
MAPBOX_API_TOKEN = config('MAPBOX_API_TOKEN', default='')

# Celery Configuration
CELERY_BROKER_URL = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('REDIS_URL', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes

# Sola Payment Gateway Settings
SOLA_API_KEY = config('SOLA_API_KEY', default='')
SOLA_SANDBOX_MODE = config('SOLA_SANDBOX_MODE', default=True, cast=bool)

# Note: Sola uses the same URL for sandbox and production
# The API key determines which environment is used
SOLA_API_URL = 'https://x1.cardknox.com/gateway'
SOLA_TIMEOUT = 30  # Request timeout in seconds

# Activity Tracking Settings
ACTIVITY_TRACKING_ASYNC = config('ACTIVITY_TRACKING_ASYNC', default=True, cast=bool)  # Use async by default
ACTIVITY_TRACKING_TIMEOUT = config('ACTIVITY_TRACKING_TIMEOUT', default=5.0, cast=float)  # Async timeout in seconds
ACTIVITY_TRACKING_CLEANUP_DAYS = config('ACTIVITY_TRACKING_CLEANUP_DAYS', default=90, cast=int)

# Suppress known CKEditor 4 deprecation warning from django-ckeditor
SILENCED_SYSTEM_CHECKS = ['ckeditor.W001']
