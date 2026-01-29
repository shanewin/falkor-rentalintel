"""
SMS Phone Verification System with OTP
Provides secure phone number verification with rate limiting
"""

import random
import logging
from datetime import datetime, timedelta
from typing import Tuple, Optional, Dict
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from applications.sms_utils import SMSBackend, validate_phone_number

logger = logging.getLogger(__name__)


class PhoneVerificationService:
    """
    Manages phone verification with OTP codes and rate limiting
    """
    
    # Configuration
    OTP_LENGTH = 6
    OTP_EXPIRY_MINUTES = 10
    MAX_ATTEMPTS_PER_HOUR = 3
    MAX_ATTEMPTS_PER_DAY = 10
    VERIFICATION_ATTEMPTS_LIMIT = 5
    RATE_LIMIT_WINDOW_HOURS = 1
    
    def __init__(self):
        self.sms_backend = SMSBackend()
    
    def generate_otp(self) -> str:
        """Generate a random 6-digit OTP code"""
        return str(random.randint(100000, 999999))
    
    def _get_cache_keys(self, phone_number: str) -> Dict[str, str]:
        """Get cache keys for various verification data"""
        return {
            'otp': f"sms_otp:{phone_number}",
            'attempts_hour': f"sms_attempts_hour:{phone_number}",
            'attempts_day': f"sms_attempts_day:{phone_number}",
            'verify_attempts': f"sms_verify_attempts:{phone_number}",
            'verified': f"sms_verified:{phone_number}",
            'blocked': f"sms_blocked:{phone_number}"
        }
    
    def is_rate_limited(self, phone_number: str) -> Tuple[bool, Optional[str]]:
        """
        Check if phone number has exceeded rate limits
        
        Returns:
            Tuple of (is_limited, error_message)
        """
        keys = self._get_cache_keys(phone_number)
        
        # Check if blocked
        if cache.get(keys['blocked']):
            return True, "This phone number has been temporarily blocked due to too many attempts."
        
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
        phone_number: str, 
        user=None,
        purpose: str = "verification"
    ) -> Tuple[bool, str]:
        """
        Send OTP verification code via SMS
        
        Args:
            phone_number: Phone number to verify
            user: Optional user object for logging
            purpose: Purpose of verification (verification, 2fa, password_reset)
        
        Returns:
            Tuple of (success, message)
        """
        # Validate phone number format
        is_valid, formatted_phone = validate_phone_number(phone_number)
        if not is_valid:
            return False, formatted_phone
        
        # Check rate limiting
        is_limited, limit_message = self.is_rate_limited(formatted_phone)
        if is_limited:
            logger.warning(f"Rate limit exceeded for {formatted_phone}: {limit_message}")
            return False, limit_message
        
        # Check if SMS backend is configured
        if not self.sms_backend.enabled:
            return False, "SMS service is not configured. Please contact support."
        
        try:
            # Generate OTP
            otp_code = self.generate_otp()
            
            # Get cache keys
            keys = self._get_cache_keys(formatted_phone)
            
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
            
            # Compose message based on purpose
            if purpose == "verification":
                message = f"Your {settings.SITE_NAME} verification code is: {otp_code}\n\nThis code expires in {self.OTP_EXPIRY_MINUTES} minutes."
            elif purpose == "2fa":
                message = f"Your {settings.SITE_NAME} login code is: {otp_code}\n\nDo not share this code with anyone."
            elif purpose == "password_reset":
                message = f"Your {settings.SITE_NAME} password reset code is: {otp_code}\n\nIf you didn't request this, please ignore."
            else:
                message = f"Your {settings.SITE_NAME} verification code is: {otp_code}"
            
            # Send SMS
            success, result = self.sms_backend.send_sms(formatted_phone, message)
            
            if success:
                logger.info(f"OTP sent successfully to {formatted_phone} for {purpose}")
                remaining_attempts = self.MAX_ATTEMPTS_PER_HOUR - hourly_attempts
                return True, f"Verification code sent. You have {remaining_attempts} attempts remaining this hour."
            else:
                # Remove OTP from cache if sending failed
                cache.delete(keys['otp'])
                return False, f"Failed to send SMS: {result}"
                
        except Exception as e:
            logger.error(f"Error sending OTP to {formatted_phone}: {e}")
            return False, "An error occurred while sending the verification code."
    
    def verify_code(
        self, 
        phone_number: str, 
        code: str,
        purpose: str = "verification"
    ) -> Tuple[bool, str]:
        """
        Verify the OTP code
        
        Args:
            phone_number: Phone number being verified
            code: OTP code to verify
            purpose: Expected purpose of verification
        
        Returns:
            Tuple of (success, message)
        """
        # Validate phone number format
        is_valid, formatted_phone = validate_phone_number(phone_number)
        if not is_valid:
            return False, "Invalid phone number format"
        
        # Get cache keys
        keys = self._get_cache_keys(formatted_phone)
        
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
            
            logger.info(f"Phone {formatted_phone} successfully verified for {purpose}")
            return True, "Phone number successfully verified!"
        else:
            # Increment failed attempts
            cache.set(keys['verify_attempts'], verify_attempts + 1, 600)  # 10 minutes
            remaining = self.VERIFICATION_ATTEMPTS_LIMIT - verify_attempts - 1
            return False, f"Invalid verification code. {remaining} attempts remaining."
    
    def is_verified(self, phone_number: str) -> bool:
        """
        Check if a phone number has been recently verified
        
        Args:
            phone_number: Phone number to check
        
        Returns:
            True if verified within last 24 hours
        """
        is_valid, formatted_phone = validate_phone_number(phone_number)
        if not is_valid:
            return False
        
        keys = self._get_cache_keys(formatted_phone)
        return cache.get(keys['verified']) is not None
    
    def resend_code(self, phone_number: str, user=None) -> Tuple[bool, str]:
        """
        Resend verification code with rate limiting
        
        Args:
            phone_number: Phone number to send code to
            user: Optional user object
        
        Returns:
            Tuple of (success, message)
        """
        # Check if there's an existing valid OTP
        is_valid, formatted_phone = validate_phone_number(phone_number)
        if not is_valid:
            return False, formatted_phone
        
        keys = self._get_cache_keys(formatted_phone)
        existing_otp = cache.get(keys['otp'])
        
        if existing_otp:
            created_at = datetime.fromisoformat(existing_otp['created_at'])
            time_passed = (timezone.now() - created_at).total_seconds()
            
            # Don't allow resend within 60 seconds
            if time_passed < 60:
                wait_time = 60 - int(time_passed)
                return False, f"Please wait {wait_time} seconds before requesting a new code."
        
        # Send new code
        return self.send_verification_code(formatted_phone, user)
    
    def clear_verification(self, phone_number: str):
        """
        Clear all verification data for a phone number
        Used when phone number changes or for admin reset
        """
        is_valid, formatted_phone = validate_phone_number(phone_number)
        if not is_valid:
            return
        
        keys = self._get_cache_keys(formatted_phone)
        for key in keys.values():
            cache.delete(key)
    
    def get_verification_status(self, phone_number: str) -> Dict:
        """
        Get detailed verification status for debugging/admin
        
        Args:
            phone_number: Phone number to check
        
        Returns:
            Dictionary with verification status details
        """
        is_valid, formatted_phone = validate_phone_number(phone_number)
        if not is_valid:
            return {'valid': False, 'error': formatted_phone}
        
        keys = self._get_cache_keys(formatted_phone)
        
        return {
            'valid': True,
            'phone_number': formatted_phone,
            'has_pending_otp': cache.get(keys['otp']) is not None,
            'is_verified': cache.get(keys['verified']) is not None,
            'is_blocked': cache.get(keys['blocked']) is not None,
            'hourly_attempts': cache.get(keys['attempts_hour'], 0),
            'daily_attempts': cache.get(keys['attempts_day'], 0),
            'verify_attempts': cache.get(keys['verify_attempts'], 0)
        }


# Singleton instance
phone_verification_service = PhoneVerificationService()


# Convenience functions
def send_phone_verification(phone_number: str, user=None) -> Tuple[bool, str]:
    """Send phone verification code"""
    return phone_verification_service.send_verification_code(phone_number, user)


def verify_phone_code(phone_number: str, code: str) -> Tuple[bool, str]:
    """Verify phone verification code"""
    return phone_verification_service.verify_code(phone_number, code)


def is_phone_verified(phone_number: str) -> bool:
    """Check if phone is verified"""
    return phone_verification_service.is_verified(phone_number)


def resend_verification_code(phone_number: str, user=None) -> Tuple[bool, str]:
    """Resend verification code"""
    return phone_verification_service.resend_code(phone_number, user)