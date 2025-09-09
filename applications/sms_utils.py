"""
SMS sending utilities using Twilio
Complements the existing email system
"""

import logging
from django.conf import settings
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class SMSBackend:
    """
    Twilio SMS backend for sending application notifications
    """
    
    def __init__(self):
        self.enabled = self._is_configured()
        if self.enabled:
            try:
                from twilio.rest import Client
                self.client = Client(
                    settings.TWILIO_ACCOUNT_SID,
                    settings.TWILIO_AUTH_TOKEN
                )
            except ImportError:
                logger.error("Twilio package not installed. Run: pip install twilio")
                self.enabled = False
            except Exception as e:
                logger.error(f"Twilio initialization failed: {e}")
                self.enabled = False
    
    def _is_configured(self) -> bool:
        """Check if Twilio is properly configured"""
        required_settings = [
            'TWILIO_ACCOUNT_SID',
            'TWILIO_AUTH_TOKEN', 
            'TWILIO_FROM_PHONE'
        ]
        
        for setting in required_settings:
            value = getattr(settings, setting, '')
            if not value or value.startswith('your-'):
                return False
        
        return True
    
    def send_sms(self, to_phone: str, message: str) -> Tuple[bool, str]:
        """
        Send SMS message
        
        Args:
            to_phone: Recipient phone number (E.164 format recommended)
            message: SMS message content
            
        Returns:
            Tuple of (success: bool, message_id_or_error: str)
        """
        if not self.enabled:
            return False, "SMS not configured. Please add Twilio credentials."
        
        try:
            # Ensure phone number formatting
            if not to_phone.startswith('+'):
                # Assume US number if no country code
                to_phone = f"+1{to_phone.replace('-', '').replace('(', '').replace(')', '').replace(' ', '')}"
            
            message = self.client.messages.create(
                body=message,
                from_=settings.TWILIO_FROM_PHONE,
                to=to_phone
            )
            
            logger.info(f"SMS sent successfully via Twilio to {to_phone}")
            return True, message.sid
            
        except Exception as e:
            error_msg = f"SMS sending failed: {str(e)}"
            logger.error(error_msg)
            return False, error_msg


def send_application_link_sms(to_phone: str, application) -> Tuple[bool, str]:
    """
    Send application link via SMS
    
    Args:
        to_phone: Recipient phone number
        application: Application instance
        
    Returns:
        Tuple of (success: bool, message_id_or_error: str)
    """
    sms_backend = SMSBackend()
    
    if not sms_backend.enabled:
        return False, "SMS service not configured"
    
    # Create SMS message
    site_url = getattr(settings, 'SITE_URL', 'http://localhost:8000')
    application_url = f"{site_url}/applications/{application.unique_link}/"
    
    # Build property info
    if application.apartment:
        property_info = f"{application.apartment.building.name} - Unit {application.apartment.unit_number}"
    else:
        property_info = f"{application.get_building_display()}"
        if application.get_unit_display():
            property_info += f" - Unit {application.get_unit_display()}"
    
    # SMS template (keep under 160 characters for single SMS)
    message = f"DoorWay: Complete your application for {property_info}. Link: {application_url}"
    
    return sms_backend.send_sms(to_phone, message)


def send_test_sms(to_phone: str) -> Tuple[bool, str]:
    """
    Send test SMS message
    
    Args:
        to_phone: Test recipient phone number
        
    Returns:
        Tuple of (success: bool, message_id_or_error: str)
    """
    sms_backend = SMSBackend()
    
    if not sms_backend.enabled:
        return False, "SMS service not configured"
    
    message = "This is a test SMS from DoorWay. If you received this, SMS is working!"
    
    return sms_backend.send_sms(to_phone, message)


def validate_phone_number(phone: str) -> Tuple[bool, str]:
    """
    Validate and format phone number
    
    Args:
        phone: Phone number to validate
        
    Returns:
        Tuple of (is_valid: bool, formatted_phone_or_error: str)
    """
    if not phone:
        return False, "Phone number is required"
    
    # Remove common formatting
    cleaned = phone.replace('-', '').replace('(', '').replace(')', '').replace(' ', '').replace('.', '')
    
    # Check if it starts with country code
    if cleaned.startswith('+'):
        if len(cleaned) >= 10:
            return True, cleaned
        else:
            return False, "Phone number too short"
    
    # Assume US number
    if len(cleaned) == 10:
        return True, f"+1{cleaned}"
    elif len(cleaned) == 11 and cleaned.startswith('1'):
        return True, f"+{cleaned}"
    else:
        return False, "Invalid phone number format. Use 10-digit US format or include country code."


def get_sms_status() -> dict:
    """
    Get SMS configuration status
    
    Returns:
        Dictionary with SMS configuration information
    """
    sms_backend = SMSBackend()
    
    return {
        'configured': sms_backend.enabled,
        'account_sid': getattr(settings, 'TWILIO_ACCOUNT_SID', '')[:8] + '...' if sms_backend.enabled else 'Not configured',
        'from_phone': getattr(settings, 'TWILIO_FROM_PHONE', 'Not configured'),
        'status': 'Ready' if sms_backend.enabled else 'Needs configuration'
    }