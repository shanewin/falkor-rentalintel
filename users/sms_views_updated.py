"""
Updated phone verification view with account activation
Shows BEFORE and AFTER for comparison
"""

# ============================================
# CURRENT VERSION (Basic verification only)
# ============================================

def phone_verification_view_OLD(request, phone_number=None):
    """
    Phone verification page with OTP entry
    """
    # Get phone number from session or parameter
    if not phone_number:
        phone_number = request.session.get('pending_phone_verification')
    
    if not phone_number:
        messages.error(request, "No phone number to verify")
        return redirect('register_applicant')
    
    if request.method == 'POST':
        form = PhoneVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['verification_code']
            
            # Verify the code
            success, message = verify_phone_code(phone_number, code)
            
            if success:
                # Update user's SMS preferences if logged in
                if request.user.is_authenticated:
                    prefs, created = SMSPreferences.objects.get_or_create(
                        user=request.user,
                        defaults={'phone_number': phone_number}
                    )
                    prefs.verify_phone(request.META.get('REMOTE_ADDR'))
                    
                    # Log verification
                    SMSVerificationLog.objects.create(
                        user=request.user,
                        phone_number=phone_number,
                        status='verified',
                        purpose='registration',
                        ip_address=request.META.get('REMOTE_ADDR'),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        verified_at=timezone.now()
                    )
                
                # Clear session
                request.session.pop('pending_phone_verification', None)
                
                messages.success(request, "Phone number verified successfully!")
                
                # Redirect based on user status
                if request.user.is_authenticated:
                    return redirect('applicant_dashboard')
                else:
                    return redirect('login')
            else:
                messages.error(request, message)
    else:
        form = PhoneVerificationForm()
    
    context = {
        'form': form,
        'phone_number': phone_number
    }
    
    return render(request, 'users/phone_verification.html', context)


# ============================================
# NEW VERSION (With account activation)
# ============================================

def phone_verification_view_NEW(request, phone_number=None):
    """
    Phone verification page with OTP entry and account activation
    """
    from django.contrib.auth import authenticate, login
    from .sms_verification import verify_phone_code
    from .sms_forms import PhoneVerificationForm
    from .sms_models import SMSPreferences, SMSVerificationLog
    from .models import User
    from django.utils import timezone
    
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