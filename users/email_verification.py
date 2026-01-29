"""
Email Verification System with OTP
Provides secure email verification as the primary authentication method
"""

import random
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class EmailVerificationService:
    """
    Manages email verification with OTP codes and rate limiting
    Primary verification method - required for all users
    """
    
    # Configuration
    OTP_LENGTH = 6
    OTP_EXPIRY_MINUTES = 10
    MAX_ATTEMPTS_PER_HOUR = 3
    MAX_ATTEMPTS_PER_DAY = 10
    VERIFICATION_ATTEMPTS_LIMIT = 5
    RATE_LIMIT_WINDOW_HOURS = 1
    
    def generate_otp(self) -> str:
        """Generate a random 6-digit OTP code"""
        return str(random.randint(100000, 999999))
    
    def _get_cache_keys(self, email: str) -> Dict[str, str]:
        """Get cache keys for various verification data"""
        # Use email instead of phone for cache keys
        safe_email = email.replace('@', '_at_').replace('.', '_dot_')
        return {
            'otp': f"email_otp:{safe_email}",
            'attempts_hour': f"email_attempts_hour:{safe_email}",
            'attempts_day': f"email_attempts_day:{safe_email}",
            'verify_attempts': f"email_verify_attempts:{safe_email}",
            'verified': f"email_verified:{safe_email}",
            'blocked': f"email_blocked:{safe_email}"
        }
    
    def is_rate_limited(self, email: str) -> Tuple[bool, Optional[str]]:
        """
        Check if email has exceeded rate limits
        
        Returns:
            Tuple of (is_limited, error_message)
        """
        keys = self._get_cache_keys(email)
        
        # Check if blocked
        if cache.get(keys['blocked']):
            return True, "This email has been temporarily blocked due to too many attempts."
        
        # Check hourly limit
        hourly_attempts = cache.get(keys['attempts_hour'], 0)
        if hourly_attempts >= self.MAX_ATTEMPTS_PER_HOUR:
            return True, f"Too many verification attempts. Please try again in an hour."
        
        # Check daily limit
        daily_attempts = cache.get(keys['attempts_day'], 0)
        if daily_attempts >= self.MAX_ATTEMPTS_PER_DAY:
            # Block for 24 hours
            cache.set(keys['blocked'], True, 86400)
            return True, "Daily limit exceeded. Please try again tomorrow."
        
        return False, None
    
    def send_verification_code(
        self, 
        email: str, 
        user=None,
        purpose: str = "registration"
    ) -> Tuple[bool, str]:
        """
        Send OTP verification code via email
        
        Args:
            email: Email address to verify
            user: Optional user object for logging
            purpose: Purpose of verification (registration, password_reset, email_change)
        
        Returns:
            Tuple of (success, message)
        """
        # Validate email format (basic check - Django already validates)
        if not email or '@' not in email:
            return False, "Invalid email address"
        
        # Check rate limiting
        is_limited, limit_message = self.is_rate_limited(email)
        if is_limited:
            logger.warning(f"Rate limit exceeded for {email}: {limit_message}")
            return False, limit_message
        
        try:
            # Generate OTP
            otp_code = self.generate_otp()
            
            # Get cache keys
            keys = self._get_cache_keys(email)
            
            # Store OTP with expiry
            cache.set(keys['otp'], {
                'code': otp_code,
                'purpose': purpose,
                'created_at': timezone.now().isoformat(),
                'user_id': user.id if user else None
            }, self.OTP_EXPIRY_MINUTES * 60)
            
            # Update rate limiting counters
            hourly_attempts = cache.get(keys['attempts_hour'], 0) + 1
            daily_attempts = cache.get(keys['attempts_day'], 0) + 1
            cache.set(keys['attempts_hour'], hourly_attempts, 3600)  # 1 hour
            cache.set(keys['attempts_day'], daily_attempts, 86400)  # 24 hours
            
            # Prepare email context
            context = {
                'otp_code': otp_code,
                'purpose': purpose,
                'expiry_minutes': self.OTP_EXPIRY_MINUTES,
                'user': user
            }
            
            # Render email templates
            html_message = render_to_string('users/emails/email_verification.html', context)
            plain_message = strip_tags(html_message)
            
            # Compose subject based on purpose
            if purpose == "registration":
                subject = f"Verify Your {settings.SITE_NAME} Account - {otp_code}"
            elif purpose == "password_reset":
                subject = f"Password Reset Code - {otp_code}"
            elif purpose == "email_change":
                subject = f"Confirm Email Change - {otp_code}"
            else:
                subject = f"Your {settings.SITE_NAME} Verification Code - {otp_code}"
            
            # Send email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                html_message=html_message,
                fail_silently=False,
            )
            
            logger.info(f"Email OTP sent successfully to {email} for {purpose}")
            remaining_attempts = self.MAX_ATTEMPTS_PER_HOUR - hourly_attempts
            return True, f"Verification code sent to {email}. You have {remaining_attempts} attempts remaining this hour."
            
        except Exception as e:
            logger.error(f"Error sending email OTP to {email}: {e}")
            # Remove OTP from cache if sending failed
            keys = self._get_cache_keys(email)
            cache.delete(keys['otp'])
            return False, "Failed to send verification email. Please try again."
    
    def verify_code(
        self, 
        email: str, 
        code: str,
        purpose: str = "registration"
    ) -> Tuple[bool, str]:
        """
        Verify the OTP code
        
        Args:
            email: Email address being verified
            code: OTP code to verify
            purpose: Expected purpose of verification
        
        Returns:
            Tuple of (success, message)
        """
        # Validate email
        if not email or '@' not in email:
            return False, "Invalid email address"
        
        # Get cache keys
        keys = self._get_cache_keys(email)
        
        # Check verification attempts
        verify_attempts = cache.get(keys['verify_attempts'], 0)
        if verify_attempts >= self.VERIFICATION_ATTEMPTS_LIMIT:
            cache.delete(keys['otp'])  # Invalidate OTP
            return False, "Too many incorrect attempts. Please request a new code."
        
        # Get stored OTP data
        otp_data = cache.get(keys['otp'])
        if not otp_data:
            return False, "No verification code found or code has expired."
        
        # Check purpose matches
        if otp_data.get('purpose') != purpose:
            return False, "Invalid verification context."
        
        # Verify code
        if otp_data.get('code') == code:
            # Success! Mark as verified
            cache.set(keys['verified'], {
                'verified_at': timezone.now().isoformat(),
                'purpose': purpose
            }, 86400)  # Valid for 24 hours
            
            # Clean up
            cache.delete(keys['otp'])
            cache.delete(keys['verify_attempts'])
            
            logger.info(f"Email {email} successfully verified for {purpose}")
            return True, "Email successfully verified!"
        else:
            # Increment failed attempts
            cache.set(keys['verify_attempts'], verify_attempts + 1, 600)  # 10 minutes
            remaining = self.VERIFICATION_ATTEMPTS_LIMIT - verify_attempts - 1
            return False, f"Invalid verification code. {remaining} attempts remaining."
    
    def is_verified(self, email: str) -> bool:
        """
        Check if an email has been recently verified
        
        Args:
            email: Email address to check
        
        Returns:
            True if verified within last 24 hours
        """
        if not email or '@' not in email:
            return False
        
        keys = self._get_cache_keys(email)
        return cache.get(keys['verified']) is not None
    
    def resend_code(self, email: str, user=None, purpose: str = "registration") -> Tuple[bool, str]:
        """
        Resend verification code with rate limiting
        
        Args:
            email: Email address to send code to
            user: Optional user object
            purpose: Purpose of verification
        
        Returns:
            Tuple of (success, message)
        """
        # Check if there's an existing valid OTP
        keys = self._get_cache_keys(email)
        existing_otp = cache.get(keys['otp'])
        
        if existing_otp:
            created_at = datetime.fromisoformat(existing_otp['created_at'])
            time_passed = (timezone.now() - created_at).total_seconds()
            
            # Don't allow resend within 60 seconds
            if time_passed < 60:
                wait_time = 60 - int(time_passed)
                return False, f"Please wait {wait_time} seconds before requesting a new code."
        
        # Send new code
        return self.send_verification_code(email, user, purpose)
    
    def clear_verification(self, email: str):
        """
        Clear all verification data for an email
        Used when email changes or for admin reset
        """
        if not email or '@' not in email:
            return
        
        keys = self._get_cache_keys(email)
        for key in keys.values():
            cache.delete(key)
    
    def get_verification_status(self, email: str) -> Dict:
        """
        Get detailed verification status for debugging/admin
        
        Args:
            email: Email address to check
        
        Returns:
            Dictionary with verification status details
        """
        if not email or '@' not in email:
            return {'valid': False, 'error': 'Invalid email address'}
        
        keys = self._get_cache_keys(email)
        
        return {
            'valid': True,
            'email': email,
            'has_pending_otp': cache.get(keys['otp']) is not None,
            'is_verified': cache.get(keys['verified']) is not None,
            'is_blocked': cache.get(keys['blocked']) is not None,
            'hourly_attempts': cache.get(keys['attempts_hour'], 0),
            'daily_attempts': cache.get(keys['attempts_day'], 0),
            'verify_attempts': cache.get(keys['verify_attempts'], 0)
        }


# Singleton instance
email_verification_service = EmailVerificationService()


# Convenience functions
def send_email_verification(email: str, user=None, purpose="registration") -> Tuple[bool, str]:
    """Send email verification code"""
    return email_verification_service.send_verification_code(email, user, purpose)


def verify_email_code(email: str, code: str, purpose="registration") -> Tuple[bool, str]:
    """Verify email verification code"""
    return email_verification_service.verify_code(email, code, purpose)


def is_email_verified(email: str) -> bool:
    """Check if email is verified"""
    return email_verification_service.is_verified(email)


def resend_email_verification(email: str, user=None, purpose="registration") -> Tuple[bool, str]:
    """Resend verification code"""
    return email_verification_service.resend_code(email, user, purpose)