"""
Professional email backends for transactional emails
Supports SendGrid, Mailgun, and Amazon SES
"""

import logging
from django.core.mail.backends.base import BaseEmailBackend
from django.conf import settings
from django.core.mail.message import EmailMessage, EmailMultiAlternatives
from typing import List

logger = logging.getLogger(__name__)


class SendGridBackend(BaseEmailBackend):
    """
    SendGrid email backend for reliable transactional emails
    """
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        try:
            import sendgrid
            from sendgrid.helpers.mail import Mail, From, To, Subject, Content
            self.sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
            self.Mail = Mail
            self.From = From
            self.To = To
            self.Subject = Subject
            self.Content = Content
        except ImportError:
            if not fail_silently:
                raise ImportError("SendGrid package not installed. Run: pip install sendgrid")
        except Exception as e:
            logger.error(f"SendGrid backend initialization failed: {e}")
            if not fail_silently:
                raise
    
    def send_messages(self, email_messages: List[EmailMessage]) -> int:
        """Send multiple email messages"""
        if not email_messages:
            return 0
        
        sent_count = 0
        for message in email_messages:
            if self._send_message(message):
                sent_count += 1
        
        return sent_count
    
    def _send_message(self, message: EmailMessage) -> bool:
        """Send a single email message"""
        try:
            # Build SendGrid message
            from_email = self.From(message.from_email)
            subject = self.Subject(message.subject)
            
            # Handle recipients
            if not message.to:
                logger.warning("No recipients specified for email")
                return False
            
            # Create mail object for first recipient
            to_email = self.To(message.to[0])
            
            # Handle HTML vs plain text
            if hasattr(message, 'alternatives') and message.alternatives:
                # Has HTML alternative
                html_content = None
                for content, content_type in message.alternatives:
                    if content_type == 'text/html':
                        html_content = content
                        break
                
                if html_content:
                    mail = self.Mail(
                        from_email=from_email,
                        to_emails=to_email,
                        subject=subject,
                        html_content=html_content
                    )
                    if message.body:
                        mail.add_content(self.Content("text/plain", message.body))
                else:
                    mail = self.Mail(
                        from_email=from_email,
                        to_emails=to_email,
                        subject=subject,
                        plain_text_content=message.body
                    )
            else:
                # Plain text only
                mail = self.Mail(
                    from_email=from_email,
                    to_emails=to_email,
                    subject=subject,
                    plain_text_content=message.body
                )
            
            # Add additional recipients
            for email in message.to[1:]:
                mail.add_to(self.To(email))
            
            # Add CC recipients
            if hasattr(message, 'cc') and message.cc:
                for email in message.cc:
                    mail.add_cc(email)
            
            # Add BCC recipients
            if hasattr(message, 'bcc') and message.bcc:
                for email in message.bcc:
                    mail.add_bcc(email)
            
            # Send email
            response = self.sg.send(mail)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"Email sent successfully via SendGrid to {message.to}")
                return True
            else:
                logger.error(f"SendGrid failed with status {response.status_code}: {response.body}")
                return False
                
        except Exception as e:
            logger.error(f"SendGrid email sending failed: {e}")
            if not self.fail_silently:
                raise
            return False


class MailgunBackend(BaseEmailBackend):
    """
    Mailgun email backend for reliable transactional emails
    """
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        try:
            import requests
            self.requests = requests
            self.api_key = settings.MAILGUN_API_KEY
            self.domain = settings.MAILGUN_DOMAIN
            self.base_url = f"https://api.mailgun.net/v3/{self.domain}"
        except Exception as e:
            logger.error(f"Mailgun backend initialization failed: {e}")
            if not fail_silently:
                raise
    
    def send_messages(self, email_messages: List[EmailMessage]) -> int:
        """Send multiple email messages"""
        if not email_messages:
            return 0
        
        sent_count = 0
        for message in email_messages:
            if self._send_message(message):
                sent_count += 1
        
        return sent_count
    
    def _send_message(self, message: EmailMessage) -> bool:
        """Send a single email message"""
        try:
            data = {
                'from': message.from_email,
                'to': message.to,
                'subject': message.subject,
                'text': message.body,
            }
            
            # Add HTML content if available
            if hasattr(message, 'alternatives') and message.alternatives:
                for content, content_type in message.alternatives:
                    if content_type == 'text/html':
                        data['html'] = content
                        break
            
            # Add CC and BCC
            if hasattr(message, 'cc') and message.cc:
                data['cc'] = message.cc
            if hasattr(message, 'bcc') and message.bcc:
                data['bcc'] = message.bcc
            
            response = self.requests.post(
                f"{self.base_url}/messages",
                auth=("api", self.api_key),
                data=data
            )
            
            if response.status_code == 200:
                logger.info(f"Email sent successfully via Mailgun to {message.to}")
                return True
            else:
                logger.error(f"Mailgun failed with status {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Mailgun email sending failed: {e}")
            if not self.fail_silently:
                raise
            return False


class AmazonSESBackend(BaseEmailBackend):
    """
    Amazon SES email backend for reliable transactional emails
    """
    
    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        try:
            import boto3
            self.ses_client = boto3.client(
                'ses',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_SES_REGION
            )
        except ImportError:
            if not fail_silently:
                raise ImportError("boto3 package not installed. Run: pip install boto3")
        except Exception as e:
            logger.error(f"Amazon SES backend initialization failed: {e}")
            if not fail_silently:
                raise
    
    def send_messages(self, email_messages: List[EmailMessage]) -> int:
        """Send multiple email messages"""
        if not email_messages:
            return 0
        
        sent_count = 0
        for message in email_messages:
            if self._send_message(message):
                sent_count += 1
        
        return sent_count
    
    def _send_message(self, message: EmailMessage) -> bool:
        """Send a single email message"""
        try:
            # Build SES message
            destination = {
                'ToAddresses': message.to,
            }
            
            if hasattr(message, 'cc') and message.cc:
                destination['CcAddresses'] = message.cc
            if hasattr(message, 'bcc') and message.bcc:
                destination['BccAddresses'] = message.bcc
            
            # Build message content
            message_data = {
                'Subject': {'Data': message.subject, 'Charset': 'UTF-8'},
                'Body': {
                    'Text': {'Data': message.body, 'Charset': 'UTF-8'}
                }
            }
            
            # Add HTML content if available
            if hasattr(message, 'alternatives') and message.alternatives:
                for content, content_type in message.alternatives:
                    if content_type == 'text/html':
                        message_data['Body']['Html'] = {'Data': content, 'Charset': 'UTF-8'}
                        break
            
            response = self.ses_client.send_email(
                Source=message.from_email,
                Destination=destination,
                Message=message_data
            )
            
            if response.get('MessageId'):
                logger.info(f"Email sent successfully via Amazon SES to {message.to}")
                return True
            else:
                logger.error(f"Amazon SES failed: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Amazon SES email sending failed: {e}")
            if not self.fail_silently:
                raise
            return False


def get_email_backend():
    """
    Factory function to get the appropriate email backend based on configuration
    """
    service = getattr(settings, 'EMAIL_SERVICE', 'console').lower()
    
    if service == 'sendgrid':
        if hasattr(settings, 'SENDGRID_API_KEY') and settings.SENDGRID_API_KEY:
            return 'applications.email_backends.SendGridBackend'
    elif service == 'mailgun':
        if hasattr(settings, 'MAILGUN_API_KEY') and settings.MAILGUN_API_KEY:
            return 'applications.email_backends.MailgunBackend'
    elif service == 'ses':
        if hasattr(settings, 'AWS_ACCESS_KEY_ID') and settings.AWS_ACCESS_KEY_ID:
            return 'applications.email_backends.AmazonSESBackend'
    
    # Fallback to console for development
    return 'django.core.mail.backends.console.EmailBackend'