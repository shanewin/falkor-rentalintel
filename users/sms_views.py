"""
SMS Verification Views
Handles phone verification and SMS preference management
"""

import json
import logging
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone

from .sms_verification import (
    send_phone_verification,
    verify_phone_code,
    resend_verification_code,
    phone_verification_service
)
from .sms_models import SMSPreferences, SMSVerificationLog
from .sms_forms import PhoneVerificationForm, SMSPreferencesForm

logger = logging.getLogger(__name__)


def phone_verification_view(request, phone_number=None):
    """
    Phone verification page with OTP entry and account activation
    """
    from django.contrib.auth import authenticate, login
    from .models import User
    
    # Get phone number from session or parameter
    if not phone_number:
        phone_number = request.session.get('pending_phone_verification')
    
    if not phone_number:
        messages.error(request, "No phone number to verify")
        return redirect('register_applicant')
    
    # Check if this is part of registration flow
    pending_registration = request.session.get('pending_registration')
    
    if request.method == 'POST':
        form = PhoneVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['verification_code']
            
            # Verify the code
            success, message = verify_phone_code(phone_number, code)
            
            if success:
                user = None
                
                # Handle pending registration (new user activation)
                if pending_registration and not request.user.is_authenticated:
                    try:
                        user_id = pending_registration.get('user_id')
                        user = User.objects.get(id=user_id)
                        
                        # Activate the user account
                        user.is_active = True
                        user.save()
                        
                        # Create/update SMS preferences
                        sms_prefs, created = SMSPreferences.objects.get_or_create(
                            user=user,
                            defaults={
                                'phone_number': phone_number,
                                'phone_verified': True,
                                'phone_verified_at': timezone.now(),
                                'sms_enabled': pending_registration.get('sms_opt_in', False),
                                'tcpa_consent': pending_registration.get('tcpa_consent', False),
                                'tcpa_consent_date': timezone.now() if pending_registration.get('tcpa_consent') else None,
                                'tcpa_consent_ip': request.META.get('REMOTE_ADDR')
                            }
                        )
                        
                        if not created:
                            sms_prefs.phone_verified = True
                            sms_prefs.phone_verified_at = timezone.now()
                            sms_prefs.save()
                        
                        # Auto-login the user
                        password = pending_registration.get('password')
                        if password:
                            user = authenticate(username=user.email, password=password)
                            if user:
                                login(request, user)
                                messages.success(request, 
                                    "🎉 Your phone has been verified and account activated! "
                                    "Welcome to DoorWay!"
                                )
                            else:
                                messages.success(request, 
                                    "Phone verified and account activated! Please log in."
                                )
                                return redirect('login')
                        
                        # Clear registration session data
                        request.session.pop('pending_registration', None)
                        
                    except User.DoesNotExist:
                        messages.error(request, "Registration data not found. Please register again.")
                        return redirect('register_applicant')
                
                # Handle existing user verification
                elif request.user.is_authenticated:
                    user = request.user
                    prefs, created = SMSPreferences.objects.get_or_create(
                        user=user,
                        defaults={'phone_number': phone_number}
                    )
                    prefs.verify_phone(request.META.get('REMOTE_ADDR'))
                
                # Log verification
                if user:
                    SMSVerificationLog.objects.create(
                        user=user,
                        phone_number=phone_number,
                        status='verified',
                        purpose='registration' if pending_registration else 'verification',
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        verified_at=timezone.now()
                    )
                
                # Clear session
                request.session.pop('pending_phone_verification', None)
                
                # Redirect based on user status
                if request.user.is_authenticated:
                    # Check user role and redirect appropriately
                    if request.user.is_applicant:
                        return redirect('applicant_dashboard')
                    elif request.user.is_broker:
                        return redirect('broker_dashboard')
                    elif request.user.is_staff or request.user.is_superuser:
                        return redirect('admin_dashboard')
                    else:
                        return redirect('/')
                else:
                    return redirect('login')
            else:
                messages.error(request, message)
                
                # Log failed attempt if user exists
                if pending_registration:
                    try:
                        user_id = pending_registration.get('user_id')
                        user = User.objects.get(id=user_id)
                        log = SMSVerificationLog.objects.filter(
                            user=user,
                            phone_number=phone_number,
                            status='sent'
                        ).order_by('-created_at').first()
                        
                        if log:
                            log.attempts += 1
                            log.save()
                    except User.DoesNotExist:
                        pass
    else:
        form = PhoneVerificationForm()
    
    context = {
        'form': form,
        'phone_number': phone_number,
        'is_registration': bool(pending_registration)  # Show different UI for registration
    }
    
    return render(request, 'users/phone_verification.html', context)


@require_http_methods(["POST"])
def resend_verification_code_view(request):
    """
    AJAX endpoint to resend verification code
    """
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        
        if not phone_number:
            return JsonResponse({
                'success': False,
                'message': 'Phone number required'
            })
        
        # Resend code
        user = request.user if request.user.is_authenticated else None
        success, message = resend_verification_code(phone_number, user)
        
        return JsonResponse({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Error resending verification code: {e}")
        return JsonResponse({
            'success': False,
            'message': 'An error occurred'
        })


@login_required
def sms_preferences_view(request):
    """
    Manage SMS notification preferences
    """
    prefs, created = SMSPreferences.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = SMSPreferencesForm(request.POST)
        if form.is_valid():
            # Update preferences
            prefs.phone_number = form.cleaned_data.get('phone_number')
            prefs.sms_enabled = form.cleaned_data.get('sms_enabled')
            prefs.sms_frequency = form.cleaned_data.get('sms_frequency')
            prefs.notification_types = form.cleaned_data.get('notification_types', [])
            prefs.quiet_hours_enabled = form.cleaned_data.get('quiet_hours_enabled')
            prefs.quiet_hours_start = form.cleaned_data.get('quiet_hours_start')
            prefs.quiet_hours_end = form.cleaned_data.get('quiet_hours_end')
            
            # Handle TCPA consent
            if form.cleaned_data.get('sms_enabled') and not prefs.tcpa_consent:
                prefs.tcpa_consent = True
                prefs.tcpa_consent_date = timezone.now()
                prefs.tcpa_consent_ip = request.META.get('REMOTE_ADDR')
            
            prefs.save()
            
            # Check if phone needs verification
            if prefs.phone_number and not prefs.phone_verified:
                # Send verification code
                success, message = send_phone_verification(prefs.phone_number, request.user)
                if success:
                    request.session['pending_phone_verification'] = prefs.phone_number
                    messages.info(request, message)
                    return redirect('phone_verification', phone_number=prefs.phone_number)
                else:
                    messages.error(request, message)
            else:
                messages.success(request, "SMS preferences updated successfully!")
            
            return redirect('sms_preferences')
    else:
        # Pre-fill form with existing preferences
        initial = {
            'phone_number': prefs.phone_number,
            'phone_verified': prefs.phone_verified,
            'sms_enabled': prefs.sms_enabled,
            'sms_frequency': prefs.sms_frequency,
            'notification_types': prefs.notification_types,
            'quiet_hours_enabled': prefs.quiet_hours_enabled,
            'quiet_hours_start': prefs.quiet_hours_start,
            'quiet_hours_end': prefs.quiet_hours_end,
        }
        form = SMSPreferencesForm(initial=initial)
    
    context = {
        'form': form,
        'preferences': prefs,
        'can_send_sms': prefs.can_send_sms(),
        'sms_stats': {
            'total_sent': prefs.total_sms_sent,
            'last_sent': prefs.last_sms_sent,
            'verified': prefs.phone_verified,
            'opted_out': prefs.opted_out
        }
    }
    
    return render(request, 'users/sms_preferences.html', context)


@login_required
def verify_phone_for_user(request):
    """
    Send verification code to logged-in user's phone
    """
    prefs = SMSPreferences.objects.filter(user=request.user).first()
    
    if not prefs or not prefs.phone_number:
        messages.error(request, "Please add a phone number first")
        return redirect('sms_preferences')
    
    if prefs.phone_verified:
        messages.info(request, "Your phone is already verified")
        return redirect('sms_preferences')
    
    # Send verification code
    success, message = send_phone_verification(prefs.phone_number, request.user)
    
    if success:
        request.session['pending_phone_verification'] = prefs.phone_number
        
        # Log attempt
        SMSVerificationLog.objects.create(
            user=request.user,
            phone_number=prefs.phone_number,
            status='sent',
            purpose='settings',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        messages.success(request, message)
        return redirect('phone_verification', phone_number=prefs.phone_number)
    else:
        messages.error(request, message)
        return redirect('sms_preferences')


@csrf_exempt
@require_http_methods(["POST"])
def twilio_webhook(request):
    """
    Webhook endpoint for Twilio SMS status updates
    Handles delivery confirmations and opt-outs
    """
    try:
        # Parse Twilio webhook data
        message_sid = request.POST.get('MessageSid')
        message_status = request.POST.get('MessageStatus')
        from_number = request.POST.get('From')
        body = request.POST.get('Body', '').upper()
        
        # Handle opt-out commands
        if body in ['STOP', 'UNSUBSCRIBE', 'CANCEL', 'END', 'QUIT']:
            # Find user by phone number
            prefs = SMSPreferences.objects.filter(
                phone_number=from_number
            ).first()
            
            if prefs:
                prefs.record_opt_out()
                logger.info(f"User opted out via SMS: {from_number}")
        
        # Update message status if we have the SID
        if message_sid:
            from .sms_models import SMSMessage
            msg = SMSMessage.objects.filter(sms_sid=message_sid).first()
            if msg:
                msg.status = message_status
                if message_status == 'delivered':
                    msg.delivered_at = timezone.now()
                msg.save()
        
        return JsonResponse({'status': 'ok'})
        
    except Exception as e:
        logger.error(f"Twilio webhook error: {e}")
        return JsonResponse({'status': 'error'}, status=500)


@login_required
def sms_verification_status(request):
    """
    Check verification status for current user (AJAX endpoint)
    """
    prefs = SMSPreferences.objects.filter(user=request.user).first()
    
    if not prefs:
        return JsonResponse({
            'has_phone': False,
            'verified': False
        })
    
    status = phone_verification_service.get_verification_status(
        prefs.phone_number
    ) if prefs.phone_number else {}
    
    return JsonResponse({
        'has_phone': bool(prefs.phone_number),
        'verified': prefs.phone_verified,
        'can_send_sms': prefs.can_send_sms(),
        'details': status
    })