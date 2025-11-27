import logging
import json
import time
from decimal import Decimal
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode
import requests
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

class SolaPaymentGateway:
    """
    Sola (formerly Cardknox) payment gateway integration.
    Handles card payments, tokenization, and refunds.
    """
    
    # Response codes
    RESULT_APPROVED = 'A'
    RESULT_DECLINED = 'D'
    RESULT_ERROR = 'E'
    
    # API commands
    COMMAND_SALE = 'cc:sale'
    COMMAND_AUTH = 'cc:authonly'
    COMMAND_CAPTURE = 'cc:capture'
    COMMAND_REFUND = 'cc:refund'
    COMMAND_VOID = 'cc:void'
    COMMAND_SAVE = 'cc:save'
    
    def __init__(self):
        """Initialize with settings from Django config"""
        self.api_key = getattr(settings, 'SOLA_API_KEY', '')
        self.api_url = getattr(settings, 'SOLA_API_URL', 'https://x1.cardknox.com/gateway')
        self.timeout = getattr(settings, 'SOLA_TIMEOUT', 30)
        self.is_sandbox = getattr(settings, 'SOLA_SANDBOX_MODE', True)
        
        if not self.api_key:
            logger.error("SOLA_API_KEY not configured in settings")
    
    def _log_transaction(self, action: str, request_data: Dict, response_data: Dict):
        """Log transaction details for auditing"""
        # Mask sensitive data
        safe_request = request_data.copy()
        if 'xCardNum' in safe_request:
            safe_request['xCardNum'] = f"****{safe_request['xCardNum'][-4:]}"
        if 'xCVV' in safe_request:
            safe_request['xCVV'] = '***'
        
        logger.info(f"Sola {action} - Request: {safe_request}")
        logger.info(f"Sola {action} - Response: {response_data}")
    
    def _make_request(self, data: Dict) -> Dict:
        """Make HTTP request to Sola API"""
        # Add API key to all requests
        data['xKey'] = self.api_key
        data['xVersion'] = '5.0.0'
        data['xSoftwareName'] = 'DoorWay'
        data['xSoftwareVersion'] = '1.0'
        
        try:
            response = requests.post(
                self.api_url,
                data=data,
                timeout=self.timeout,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            response.raise_for_status()
            
            # Parse form-encoded response
            result = {}
            for line in response.text.split('&'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    result[key] = value
            
            return result
            
        except requests.exceptions.Timeout:
            logger.error(f"Sola API timeout after {self.timeout} seconds")
            return {'xResult': self.RESULT_ERROR, 'xError': 'Gateway timeout'}
        except requests.exceptions.RequestException as e:
            logger.error(f"Sola API request failed: {e}")
            return {'xResult': self.RESULT_ERROR, 'xError': str(e)}
    
    def process_payment(
        self,
        amount: Decimal,
        card_number: str,
        exp_month: str,
        exp_year: str,
        cvv: str,
        cardholder_name: str,
        email: str,
        invoice_number: str = None,
        save_card: bool = False
    ) -> Tuple[bool, Dict]:
        """
        Process a credit card payment.
        
        Returns:
            Tuple of (success: bool, response_data: dict)
        """
        # Format expiration date (MMYY)
        exp_date = f"{exp_month.zfill(2)}{exp_year[-2:]}"
        
        # Build request data
        request_data = {
            'xCommand': self.COMMAND_SALE,
            'xAmount': str(amount),
            'xCardNum': card_number.replace(' ', ''),
            'xExp': exp_date,
            'xCVV': cvv,
            'xName': cardholder_name,
            'xEmail': email,
            'xInvoice': invoice_number or f"APP-{int(time.time())}",
            'xDescription': 'Rental Application Fee',
        }
        
        # Add tokenization if requested
        if save_card:
            request_data['xAllowDuplicate'] = 'TRUE'
            request_data['xTokenize'] = 'TRUE'
        
        # Make API request
        response = self._make_request(request_data)
        
        # Log transaction
        self._log_transaction('PAYMENT', request_data, response)
        
        # Check if payment was successful
        success = response.get('xResult') == self.RESULT_APPROVED
        
        # Build standardized response
        result = {
            'success': success,
            'transaction_id': response.get('xRefNum', ''),
            'auth_code': response.get('xAuthCode', ''),
            'card_token': response.get('xToken', '') if save_card else '',
            'masked_card': response.get('xMaskedCardNumber', f"****{card_number[-4:]}"),
            'response_code': response.get('xResult', ''),
            'response_text': response.get('xStatus', response.get('xError', 'Unknown error')),
            'avs_result': response.get('xAvsResult', ''),
            'cvv_result': response.get('xCvvResult', ''),
            'raw_response': response
        }
        
        return success, result
    
    def process_tokenized_payment(
        self,
        amount: Decimal,
        card_token: str,
        invoice_number: str = None
    ) -> Tuple[bool, Dict]:
        """
        Process payment using a saved card token.
        """
        request_data = {
            'xCommand': self.COMMAND_SALE,
            'xAmount': str(amount),
            'xToken': card_token,
            'xInvoice': invoice_number or f"APP-{int(time.time())}",
            'xDescription': 'Rental Application Fee',
        }
        
        response = self._make_request(request_data)
        self._log_transaction('TOKENIZED_PAYMENT', request_data, response)
        
        success = response.get('xResult') == self.RESULT_APPROVED
        
        result = {
            'success': success,
            'transaction_id': response.get('xRefNum', ''),
            'auth_code': response.get('xAuthCode', ''),
            'response_code': response.get('xResult', ''),
            'response_text': response.get('xStatus', response.get('xError', 'Unknown error')),
            'raw_response': response
        }
        
        return success, result
    
    def refund_payment(
        self,
        transaction_id: str,
        amount: Optional[Decimal] = None,
        reason: str = ''
    ) -> Tuple[bool, Dict]:
        """
        Refund a previous payment (full or partial).
        """
        request_data = {
            'xCommand': self.COMMAND_REFUND,
            'xRefNum': transaction_id,
        }
        
        # Add amount for partial refund
        if amount:
            request_data['xAmount'] = str(amount)
        
        # Add reason if provided
        if reason:
            request_data['xDescription'] = reason[:100]  # Limit length
        
        response = self._make_request(request_data)
        self._log_transaction('REFUND', request_data, response)
        
        success = response.get('xResult') == self.RESULT_APPROVED
        
        result = {
            'success': success,
            'refund_id': response.get('xRefNum', ''),
            'response_code': response.get('xResult', ''),
            'response_text': response.get('xStatus', response.get('xError', 'Unknown error')),
            'raw_response': response
        }
        
        return success, result
    
    def void_payment(self, transaction_id: str) -> Tuple[bool, Dict]:
        """
        Void a payment (cancel before settlement).
        """
        request_data = {
            'xCommand': self.COMMAND_VOID,
            'xRefNum': transaction_id,
        }
        
        response = self._make_request(request_data)
        self._log_transaction('VOID', request_data, response)
        
        success = response.get('xResult') == self.RESULT_APPROVED
        
        result = {
            'success': success,
            'response_code': response.get('xResult', ''),
            'response_text': response.get('xStatus', response.get('xError', 'Unknown error')),
            'raw_response': response
        }
        
        return success, result
    
    def validate_card(self, card_number: str) -> bool:
        """
        Validate card number using Luhn algorithm.
        """
        card_number = card_number.replace(' ', '').replace('-', '')
        
        if not card_number.isdigit():
            return False
        
        # Luhn algorithm
        def luhn_checksum(card_num):
            def digits_of(n):
                return [int(d) for d in str(n)]
            digits = digits_of(card_num)
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(digits_of(d*2))
            return checksum % 10
        
        return luhn_checksum(card_number) == 0
    
    def get_card_type(self, card_number: str) -> str:
        """
        Determine card type from card number.
        """
        card_number = card_number.replace(' ', '').replace('-', '')
        
        if card_number.startswith('4'):
            return 'visa'
        elif card_number.startswith(('51', '52', '53', '54', '55')):
            return 'mastercard'
        elif card_number.startswith(('34', '37')):
            return 'amex'
        elif card_number.startswith('6011') or card_number.startswith('65'):
            return 'discover'
        else:
            return 'unknown'


class PaymentProcessor:
    """
    High-level payment processor that uses the Sola gateway
    and handles database operations.
    """
    
    def __init__(self):
        self.gateway = SolaPaymentGateway()
    
    def process_application_payment(
        self,
        application,
        card_data: Dict,
        amount: Optional[Decimal] = None
    ) -> Tuple[bool, str]:
        """
        Process payment for an application.
        
        Args:
            application: Application model instance
            card_data: Dictionary with card details
            amount: Override amount (uses application.application_fee_amount by default)
        
        Returns:
            Tuple of (success: bool, message: str)
        """
        from .models import ApplicationPayment, PaymentStatus
        
        # Get or create payment record
        payment, created = ApplicationPayment.objects.get_or_create(
            application=application,
            defaults={
                'amount': amount or application.application_fee_amount,
                'status': PaymentStatus.PENDING
            }
        )
        
        # Don't process if already paid
        if payment.status == PaymentStatus.COMPLETED:
            return True, "Payment already processed"
        
        # Extract card data
        card_number = card_data.get('card_number', '')
        exp_month = card_data.get('exp_month', '')
        exp_year = card_data.get('exp_year', '')
        cvv = card_data.get('cvv', '')
        cardholder_name = card_data.get('cardholder_name', '')
        
        # Get email from application
        email = ''
        if hasattr(application, 'applicant') and application.applicant:
            email = application.applicant.email
        
        # Validate card
        if not self.gateway.validate_card(card_number):
            payment.status = PaymentStatus.FAILED
            payment.save()
            return False, "Invalid card number"
        
        # Process payment
        success, response = self.gateway.process_payment(
            amount=payment.amount,
            card_number=card_number,
            exp_month=exp_month,
            exp_year=exp_year,
            cvv=cvv,
            cardholder_name=cardholder_name,
            email=email,
            invoice_number=f"APP-{application.id}",
            save_card=card_data.get('save_card', False)
        )
        
        # Update payment record
        if success:
            payment.status = PaymentStatus.COMPLETED
            payment.transaction_id = response['transaction_id']
            payment.payment_method = self.gateway.get_card_type(card_number)
            payment.paid_at = timezone.now()
            
            # Store additional details
            if response.get('card_token'):
                payment.payment_intent_id = response['card_token']
            
            payment.save()
            
            # Update application status
            application.payment_completed = True
            application.payment_completed_at = timezone.now()
            application.save()
            
            # Log activity
            from .services import log_activity
            log_activity(
                application,
                f"Payment processed successfully - ${payment.amount}"
            )
            
            return True, f"Payment of ${payment.amount} processed successfully"
        else:
            payment.status = PaymentStatus.FAILED
            payment.save()
            
            # Log failure
            from .services import log_activity
            log_activity(
                application,
                f"Payment failed: {response.get('response_text', 'Unknown error')}"
            )
            
            return False, response.get('response_text', 'Payment processing failed')
    
    def refund_application_payment(
        self,
        application,
        amount: Optional[Decimal] = None,
        reason: str = ''
    ) -> Tuple[bool, str]:
        """
        Refund an application payment.
        """
        from .models import ApplicationPayment, PaymentStatus
        
        try:
            payment = ApplicationPayment.objects.get(application=application)
        except ApplicationPayment.DoesNotExist:
            return False, "No payment found for this application"
        
        if payment.status != PaymentStatus.COMPLETED:
            return False, "Payment not completed, cannot refund"
        
        if not payment.transaction_id:
            return False, "No transaction ID found"
        
        # Process refund
        refund_amount = amount or payment.amount
        success, response = self.gateway.refund_payment(
            transaction_id=payment.transaction_id,
            amount=refund_amount,
            reason=reason
        )
        
        if success:
            payment.status = PaymentStatus.REFUNDED
            payment.refunded_at = timezone.now()
            payment.refund_amount = refund_amount
            payment.refund_reason = reason
            payment.save()
            
            # Log activity
            from .services import log_activity
            log_activity(
                application,
                f"Payment refunded - ${refund_amount}"
            )
            
            return True, f"Refund of ${refund_amount} processed successfully"
        else:
            return False, response.get('response_text', 'Refund failed')