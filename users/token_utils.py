"""
Secure token utilities for user authentication.
Business Context: Provides secure account activation and password reset
without sending passwords via email.
"""

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from datetime import datetime, timedelta
import six


class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    """
    Custom token generator for account activation.
    More secure than sending temporary passwords via email.
    """
    def _make_hash_value(self, user, timestamp):
        """
        Create hash including user's activation status to invalidate
        token after first use.
        """
        return (
            six.text_type(user.pk) + 
            six.text_type(timestamp) +
            six.text_type(user.is_active) +
            six.text_type(user.email)
        )


class InvitationTokenGenerator(PasswordResetTokenGenerator):
    """
    Token generator for user invitations.
    Allows setting initial password securely.
    """
    def _make_hash_value(self, user, timestamp):
        """
        Include password hash to invalidate token after password is set.
        """
        return (
            six.text_type(user.pk) + 
            six.text_type(timestamp) +
            six.text_type(user.password)
        )


# Create singleton instances
account_activation_token = AccountActivationTokenGenerator()
invitation_token = InvitationTokenGenerator()


def generate_activation_link(user, request=None, domain=None):
    """
    Generate a secure activation link for a user.
    
    Args:
        user: User instance
        request: HttpRequest (optional, for getting domain)
        domain: Override domain (optional)
        
    Returns:
        Full activation URL
    """
    from django.urls import reverse
    from django.conf import settings
    
    # Generate token
    token = account_activation_token.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    # Build URL
    if domain:
        base_url = f"https://{domain}"
    elif request:
        base_url = f"{'https' if request.is_secure() else 'http'}://{request.get_host()}"
    else:
        base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    activation_path = reverse('activate_account', kwargs={'uidb64': uid, 'token': token})
    return f"{base_url}{activation_path}"


def generate_invitation_link(user, request=None, domain=None):
    """
    Generate a secure invitation link for setting password.
    
    Args:
        user: User instance
        request: HttpRequest (optional, for getting domain)
        domain: Override domain (optional)
        
    Returns:
        Full invitation URL
    """
    from django.urls import reverse
    from django.conf import settings
    
    # Generate token
    token = invitation_token.make_token(user)
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    # Build URL
    if domain:
        base_url = f"https://{domain}"
    elif request:
        base_url = f"{'https' if request.is_secure() else 'http'}://{request.get_host()}"
    else:
        base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    invitation_path = reverse('set_password', kwargs={'uidb64': uid, 'token': token})
    return f"{base_url}{invitation_path}"


def verify_token(uidb64, token, token_generator):
    """
    Verify a token is valid for a user.
    
    Args:
        uidb64: Base64 encoded user ID
        token: Token string
        token_generator: Token generator instance
        
    Returns:
        User instance if valid, None otherwise
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
    
    if token_generator.check_token(user, token):
        return user
    return None


def create_secure_login_link(user, request=None, duration_hours=24):
    """
    Create a temporary secure login link (for password-less login).
    
    Args:
        user: User instance
        request: HttpRequest (optional)
        duration_hours: How long link is valid
        
    Returns:
        Secure login URL
    """
    from django.urls import reverse
    from django.conf import settings
    from django.core.signing import TimestampSigner
    
    signer = TimestampSigner()
    signed_value = signer.sign(user.pk)
    
    if request:
        base_url = f"{'https' if request.is_secure() else 'http'}://{request.get_host()}"
    else:
        base_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    
    login_path = reverse('secure_login', kwargs={'signed_value': signed_value})
    return f"{base_url}{login_path}"