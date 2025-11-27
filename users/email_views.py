"""
Email Verification Views
Handles email verification flow and related endpoints
"""

import json
import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib.auth import authenticate, login

from .email_verification import (
    email_verification_service,
    send_email_verification,
    verify_email_code,
    resend_email_verification
)
from .models import User
from .sms_forms import PhoneVerificationForm  # Reuse the same form structure

logger = logging.getLogger(__name__)


def email_verification_view(request, email=None):
    """
    Email verification page with OTP entry and account activation
    Primary verification method - required for all users
    """
    # Get email from session or parameter
    if not email:
        email = request.session.get('pending_email_verification')
    
    if not email:
        messages.error(request, "No email address to verify")
        return redirect('register_applicant')
    
    # Check if this is part of registration flow
    pending_registration = request.session.get('pending_registration')
    
    if request.method == 'POST':
        form = PhoneVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['verification_code']
            
            # Determine purpose based on context
            purpose = 'registration' if pending_registration else 'verification'
            
            # Verify the code
            success, message = verify_email_code(email, code, purpose)
            
            if success:
                logger.info("DEBUG: Verification succeeded, entering success block")
                # Handle pending registration (new user activation)
                if pending_registration and not request.user.is_authenticated:
                    logger.info("DEBUG: Processing pending registration")
                    try:
                        user_id = pending_registration.get('user_id')
                        user = User.objects.get(id=user_id)
                        
                        # Mark email as verified
                        user.email_verified = True
                        user.email_verified_at = timezone.now()
                        user.is_active = True
                        user.save()
                        
                        # Create Applicant profile
                        from applicants.models import Applicant
                        applicant, created = Applicant.objects.get_or_create(
                            email=user.email,
                            defaults={
                                'first_name': pending_registration.get('first_name', ''),
                                'last_name': pending_registration.get('last_name', ''),
                                'phone_number': pending_registration.get('phone_number', ''),
                            }
                        )
                        applicant.user = user
                        if not created:
                            applicant.first_name = pending_registration.get('first_name', applicant.first_name)
                            applicant.last_name = pending_registration.get('last_name', applicant.last_name)
                        applicant.save()

                        logger.info("DEBUG: Applicant profile created, starting auto-login")
                        
                        # Auto-login
                        password = pending_registration.get('password')
                        logger.info(f"DEBUG: Attempting auto-login for {user.email}")
                        logger.info(f"DEBUG: Password exists: {bool(password)}")

                        if password:
                            authenticated_user = authenticate(username=user.email, password=password)
                            logger.info(f"DEBUG: Authentication result: {authenticated_user}")
                            
                            if authenticated_user:
                                login(request, authenticated_user)
                                logger.info(f"DEBUG: Login successful, redirecting to dashboard")
                                
                                # Clear session
                                request.session.pop('pending_registration', None)
                                request.session.pop('pending_email_verification', None)
                                
                                # Success message
                                messages.success(request, "Your email has been verified and account activated! Welcome to DoorWay!")
                                
                                # Redirect to dashboard
                                if authenticated_user.is_applicant:
                                    logger.info("DEBUG: Redirecting to applicant_dashboard")
                                    return redirect('applicant_dashboard')
                                elif authenticated_user.is_broker:
                                    return redirect('broker_dashboard')
                                else:
                                    return redirect('/')
                            else:
                                logger.error("DEBUG: Authentication failed!")

                        # If authentication failed
                        logger.info("DEBUG: Falling through to login redirect")
                        messages.success(request, "Email verified! Please log in.")
                        return redirect('login')
                        
                    except User.DoesNotExist:
                        messages.error(request, "Registration data not found. Please register again.")
                        return redirect('register_applicant')
                
                # Handle existing user email verification
                elif request.user.is_authenticated:
                    user = request.user
                    user.email_verified = True
                    user.email_verified_at = timezone.now()
                    user.save()
                    messages.success(request, "Email successfully verified!")
                    return redirect('applicant_dashboard')
                
                # Fallback
                return redirect('login')
            else:
                messages.error(request, message)
                return redirect(request.path + '?error=invalid_code')
    else:
        form = PhoneVerificationForm()
    
    context = {
        'form': form,
        'email': email,
        'is_registration': bool(pending_registration),
        'has_phone': pending_registration.get('phone_number') if pending_registration else False
    }
    
    return render(request, 'users/email_verification.html', context)


@require_http_methods(["POST"])
def resend_email_verification_view(request):
    """
    AJAX endpoint to resend email verification code
    """
    try:
        data = json.loads(request.body)
        email = data.get('email')
        
        if not email:
            return JsonResponse({
                'success': False,
                'message': 'Email address required'
            })
        
        # Get user if exists (for logging purposes)
        user = None
        pending_registration = request.session.get('pending_registration')
        
        if pending_registration:
            user_id = pending_registration.get('user_id')
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                pass
        elif request.user.is_authenticated:
            user = request.user
        
        # Determine purpose
        purpose = 'registration' if pending_registration else 'verification'
        
        # Resend code
        success, message = resend_email_verification(email, user, purpose)
        
        return JsonResponse({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Error resending email verification code: {e}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while sending the verification code'
        })