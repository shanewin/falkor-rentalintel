from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
import sys

class Command(BaseCommand):
    help = 'Test email configuration by sending a test email'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            help='Email address to send test email to',
            required=True
        )
        parser.add_argument(
            '--type',
            type=str,
            choices=['simple', 'application'],
            default='simple',
            help='Type of test email to send (simple or application)'
        )

    def handle(self, *args, **options):
        recipient_email = options['to']
        email_type = options['type']
        
        self.stdout.write("🔧 Testing Email Configuration...")
        self.stdout.write(f"📧 Recipient: {recipient_email}")
        
        # Show current settings
        self.stdout.write("\n📋 Current Email Settings:")
        self.stdout.write(f"  EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"  EMAIL_HOST: {getattr(settings, 'EMAIL_HOST', 'Not set')}")
        self.stdout.write(f"  EMAIL_PORT: {getattr(settings, 'EMAIL_PORT', 'Not set')}")
        self.stdout.write(f"  EMAIL_USE_TLS: {getattr(settings, 'EMAIL_USE_TLS', 'Not set')}")
        self.stdout.write(f"  EMAIL_HOST_USER: {getattr(settings, 'EMAIL_HOST_USER', 'Not set')}")
        self.stdout.write(f"  EMAIL_HOST_PASSWORD: {'Set' if getattr(settings, 'EMAIL_HOST_PASSWORD', '') else 'Not set'}")
        self.stdout.write(f"  DEFAULT_FROM_EMAIL: {getattr(settings, 'DEFAULT_FROM_EMAIL', 'Not set')}")
        
        try:
            if email_type == 'simple':
                success = self.send_simple_test_email(recipient_email)
            else:
                success = self.send_application_test_email(recipient_email)
                
            if success:
                self.stdout.write(self.style.SUCCESS('\n✅ Email sent successfully!'))
                self.stdout.write("\n📌 Next Steps:")
                if 'console' in settings.EMAIL_BACKEND:
                    self.stdout.write("  • Email backend is set to 'console' - check your terminal for the email content")
                    self.stdout.write("  • Update your .env file with real Gmail credentials to send actual emails")
                else:
                    self.stdout.write("  • Check the recipient's inbox (including spam folder)")
                    self.stdout.write("  • If not received, verify your Gmail app password is correct")
            else:
                self.stdout.write(self.style.ERROR('\n❌ Email sending failed!'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Email sending failed with error: {str(e)}'))
            self.show_troubleshooting_tips()

    def send_simple_test_email(self, recipient_email):
        """Send a simple test email"""
        subject = 'DoorWay Email Test'
        message = '''
Hello!

This is a test email from your DoorWay application.

If you received this email, your email configuration is working correctly! 🎉

Technical Details:
- Sent from: Django application
- Email backend: {}
- Timestamp: {}

Best regards,
The DoorWay Team
        '''.format(settings.EMAIL_BACKEND, self.get_timestamp())
        
        html_message = '''
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background: #1a1a1a; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0;">
                <h1>DoorWay</h1>
                <p>Email Configuration Test</p>
            </div>
            <div style="background: #f8f9fa; padding: 30px; border-radius: 0 0 8px 8px;">
                <p>Hello!</p>
                <p>This is a test email from your DoorWay application.</p>
                <p><strong>If you received this email, your email configuration is working correctly! 🎉</strong></p>
                <div style="background: white; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3>Technical Details:</h3>
                    <ul>
                        <li><strong>Sent from:</strong> Django application</li>
                        <li><strong>Email backend:</strong> {}</li>
                        <li><strong>Timestamp:</strong> {}</li>
                    </ul>
                </div>
                <p>Best regards,<br>The DoorWay Team</p>
            </div>
        </body>
        </html>
        '''.format(settings.EMAIL_BACKEND, self.get_timestamp())
        
        send_mail(
            subject=subject,
            message=message,
            html_message=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        return True

    def send_application_test_email(self, recipient_email):
        """Send a test email using the application template"""
        # Import here to avoid circular imports
        from applications.models import Application, Applicant
        from applicants.models import Applicant
        from applications.email_utils import send_application_link_email
        
        # Create a mock application for testing
        mock_applicant = type('MockApplicant', (), {
            'email': recipient_email,
            'first_name': 'Test',
            'last_name': 'User'
        })()
        
        mock_application = type('MockApplication', (), {
            'id': 'TEST',
            'applicant': mock_applicant,
            'unique_link': 'test-uuid-link',
            'apartment': None,
            'manual_building_name': 'Test Building',
            'manual_building_address': '123 Test Street, Test City, NY 10001',
            'manual_unit_number': '2A',
            'application_fee_amount': 50.00,
            'required_documents': ['Photo ID', 'Bank Statement', 'Paystub'],
        })()
        
        mock_broker = type('MockBroker', (), {
            'email': 'broker@doorway.com',
            'get_full_name': lambda: 'Test Broker'
        })()
        
        mock_application.broker = mock_broker
        
        # Mock the request object
        mock_request = type('MockRequest', (), {
            'get_host': lambda: 'localhost:8000'
        })()
        
        try:
            return send_application_link_email(mock_application, mock_request)
        except Exception as e:
            self.stdout.write(f"Error with application email: {str(e)}")
            return False

    def get_timestamp(self):
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def show_troubleshooting_tips(self):
        self.stdout.write("\n🔧 Troubleshooting Tips:")
        self.stdout.write("1. Check your .env file has correct email settings")
        self.stdout.write("2. For Gmail, ensure you're using an App Password, not your regular password")
        self.stdout.write("3. Enable 2-factor authentication on Gmail first")
        self.stdout.write("4. Generate App Password: https://myaccount.google.com/apppasswords")
        self.stdout.write("5. Check if your Gmail account allows 'Less secure app access'")
        self.stdout.write("6. Verify EMAIL_USE_TLS=True for Gmail")
        self.stdout.write("7. For development, set EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend")