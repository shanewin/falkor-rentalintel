"""
Updated registration views with SMS verification integration
This shows the BEFORE and AFTER for clear comparison
"""

# ============================================
# CURRENT VERSION (WITHOUT SMS)
# ============================================

def register_applicant_OLD(request):
    """Registration view for applicants - creates both User and Applicant profile"""
    if request.user.is_authenticated:
        return redirect_by_role(request.user)
    
    if request.method == 'POST':
        form = ApplicantRegistrationForm(request.POST)
        if form.is_valid():
            # Create User account
            user = form.save(commit=False)
            user.is_applicant = True
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            # Create or update Applicant profile
            from applicants.models import Applicant
            from django.utils import timezone
            
            # Check if an applicant with this email already exists (from previous application)
            applicant, created = Applicant.objects.get_or_create(
                email=user.email,
                defaults={
                    'first_name': form.cleaned_data.get('first_name', ''),
                    'last_name': form.cleaned_data.get('last_name', ''),
                    'phone_number': form.cleaned_data.get('phone_number', ''),
                    'date_of_birth': timezone.now().date(),  # Temporary, user will update
                    'street_address_1': '',  # User will fill progressively
                    'city': '',
                    'state': 'NY',
                    'zip_code': '',
                }
            )
            
            # Link the applicant profile to the user account
            applicant.user = user
            if not created:
                # Update existing applicant with new info if provided
                applicant.first_name = form.cleaned_data.get('first_name', applicant.first_name)
                applicant.last_name = form.cleaned_data.get('last_name', applicant.last_name)
                if form.cleaned_data.get('phone_number'):
                    applicant.phone_number = form.cleaned_data['phone_number']
            applicant.save()
            
            # Auto-login after registration
            user = authenticate(username=user.email, password=form.cleaned_data['password'])
            login(request, user)
            
            messages.success(request, "Welcome! Your account has been created. You can now complete your profile.")
            return redirect('applicant_dashboard')
    else:
        form = ApplicantRegistrationForm()
    
    return render(request, 'users/register_applicant.html', {'form': form})


# ============================================
# NEW VERSION (WITH SMS VERIFICATION)
# ============================================

def register_applicant_NEW(request):
    """Registration view for applicants with SMS verification option"""
    if request.user.is_authenticated:
        return redirect_by_role(request.user)
    
    if request.method == 'POST':
        # Use the enhanced form with SMS options
        from .sms_forms import ApplicantRegistrationWithSMSForm
        form = ApplicantRegistrationWithSMSForm(request.POST)
        
        if form.is_valid():
            # Create User account
            user = form.save(commit=False)
            user.is_applicant = True
            user.set_password(form.cleaned_data['password'])
            
            # Check if user opted for SMS verification
            sms_opt_in = form.cleaned_data.get('sms_opt_in', False)
            verify_phone = form.cleaned_data.get('verify_phone', False)
            phone_number = form.cleaned_data.get('phone_number')
            tcpa_consent = form.cleaned_data.get('tcpa_consent', False)
            
            # If SMS verification requested, don't activate account yet
            if verify_phone and phone_number:
                user.is_active = False  # Account inactive until phone verified
                user.save()
                
                # Store registration data in session for after verification
                request.session['pending_registration'] = {
                    'user_id': user.id,
                    'phone_number': phone_number,
                    'sms_opt_in': sms_opt_in,
                    'tcpa_consent': tcpa_consent,
                    'first_name': form.cleaned_data.get('first_name', ''),
                    'last_name': form.cleaned_data.get('last_name', ''),
                    'password': form.cleaned_data['password']  # For auto-login after verification
                }
                
                # Send verification code
                from .sms_verification import send_phone_verification
                success, message = send_phone_verification(phone_number, user)
                
                if success:
                    # Store phone in session for verification view
                    request.session['pending_phone_verification'] = phone_number
                    
                    messages.info(request, 
                        "We've sent a verification code to your phone. "
                        "Please enter it to complete your registration."
                    )
                    return redirect('phone_verification', phone_number=phone_number)
                else:
                    # If SMS sending failed, activate account anyway
                    user.is_active = True
                    user.save()
                    messages.warning(request, 
                        f"We couldn't send a verification code ({message}). "
                        "Your account has been created without phone verification."
                    )
            else:
                # No SMS verification requested - activate immediately
                user.is_active = True
                user.save()
            
            # Create or update Applicant profile
            from applicants.models import Applicant
            from django.utils import timezone
            
            applicant, created = Applicant.objects.get_or_create(
                email=user.email,
                defaults={
                    'first_name': form.cleaned_data.get('first_name', ''),
                    'last_name': form.cleaned_data.get('last_name', ''),
                    'phone_number': phone_number or '',
                    'date_of_birth': timezone.now().date(),
                    'street_address_1': '',
                    'city': '',
                    'state': 'NY',
                    'zip_code': '',
                }
            )
            
            # Link the applicant profile to the user account
            applicant.user = user
            if not created:
                applicant.first_name = form.cleaned_data.get('first_name', applicant.first_name)
                applicant.last_name = form.cleaned_data.get('last_name', applicant.last_name)
                if phone_number:
                    applicant.phone_number = phone_number
            applicant.save()
            
            # Create SMS preferences if phone provided
            if phone_number:
                from .sms_models import SMSPreferences
                sms_prefs, _ = SMSPreferences.objects.get_or_create(
                    user=user,
                    defaults={
                        'phone_number': phone_number,
                        'sms_enabled': sms_opt_in,
                        'tcpa_consent': tcpa_consent,
                        'tcpa_consent_date': timezone.now() if tcpa_consent else None,
                        'tcpa_consent_ip': request.META.get('REMOTE_ADDR') if tcpa_consent else None
                    }
                )
            
            # Only auto-login if account is active (no verification needed)
            if user.is_active:
                user = authenticate(username=user.email, password=form.cleaned_data['password'])
                login(request, user)
                messages.success(request, 
                    "Welcome! Your account has been created. You can now complete your profile."
                )
                return redirect('applicant_dashboard')
            else:
                # User will be logged in after phone verification
                return redirect('phone_verification', phone_number=phone_number)
    else:
        from .sms_forms import ApplicantRegistrationWithSMSForm
        form = ApplicantRegistrationWithSMSForm()
    
    return render(request, 'users/register_applicant.html', {'form': form})