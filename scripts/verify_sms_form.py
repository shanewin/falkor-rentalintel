
import os
import sys
import django
from decimal import Decimal

# Setup Django environment
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.test import RequestFactory
from applicants.forms import ApplicantBasicInfoForm
from applicants.models import Applicant
from users.sms_models import SMSPreferences

User = get_user_model()

def run_verification():
    print("Starting SMS Form Verification...")
    
    # 1. Create a test user
    email = "test_sms_user@example.com"
    user, created = User.objects.get_or_create(email=email)
    if created:
        user.set_password("password123")
        user.save()
    print(f"Test user: {user.email}")
    
    # Ensure no existing preferences for clean test
    SMSPreferences.objects.filter(user=user).delete()
    
    # Ensure applicant profile exists
    applicant, _ = Applicant.objects.get_or_create(user=user)
    
    # 2. Test Case 1: Form valid with SMS Opt-in
    print("\nTest Case 1: Valid form with SMS Opt-in")
    data = {
        'first_name': 'Test',
        'last_name': 'User',
        'email': email,
        'phone_number': '555-000-1234',
        'sms_opt_in': True,
        'tcpa_consent': True,
        'verify_phone': True
    }
    
    # Create request object for the form
    factory = RequestFactory()
    request = factory.post('/applicants/my-profile/step1/')
    request.user = user
    
    form = ApplicantBasicInfoForm(data=data, instance=applicant, request=request)
    
    if form.is_valid():
        print("Form is valid.")
        form.save()
        
        # Verify SMS Preferences
        prefs = SMSPreferences.objects.get(user=user)
        print(f"SMS Preferences Created: {prefs}")
        print(f"  - Phone: {prefs.phone_number}")
        print(f"  - SMS Enabled: {prefs.sms_enabled}")
        print(f"  - TCPA Consent: {prefs.tcpa_consent}")
        
        if prefs.sms_enabled and prefs.tcpa_consent and prefs.phone_number == '555-000-1234':
            print("SUCCESS: SMS Preferences saved correctly.")
        else:
            print("FAILURE: SMS Preferences not saved correctly.")
    else:
        print("FAILURE: Form is invalid.")
        print(form.errors)

    # 3. Test Case 2: Validation Error (Opt-in without TCPA)
    print("\nTest Case 2: Validation Error (Opt-in without TCPA)")
    data_invalid = {
        'first_name': 'Test',
        'last_name': 'User',
        'email': email,
        'phone_number': '555-000-1234',
        'sms_opt_in': True,
        'tcpa_consent': False, # Missing consent
    }
    
    form_invalid = ApplicantBasicInfoForm(data=data_invalid, instance=applicant, request=request)
    
    if not form_invalid.is_valid():
        print("SUCCESS: Form correctly identified invalid state.")
        if 'tcpa_consent' in form_invalid.errors:
            print(f"  - TCPA Error found: {form_invalid.errors['tcpa_consent']}")
        else:
            print(f"  - FAILURE: TCPA error missing. Errors: {form_invalid.errors}")
    else:
         print("FAILURE: Form should be invalid but was valid.")

    # 4. Test Case 3: Load initial values
    print("\nTest Case 3: Load initial values")
    # Refresh user to ensure relations are updated
    user.refresh_from_db()
    
    # Create a fresh form instance with the user's request
    form_load = ApplicantBasicInfoForm(instance=applicant, request=request)
    
    initial_sms = form_load.fields['sms_opt_in'].initial
    initial_tcpa = form_load.fields['tcpa_consent'].initial
    
    print(f"Initial SMS Opt-in: {initial_sms}")
    print(f"Initial TCPA Consent: {initial_tcpa}")
    
    if initial_sms is True and initial_tcpa is True: # Based on Test Case 1 save
        print("SUCCESS: Initial values loaded correctly.")
    else:
        print("FAILURE: Initial values not loaded correctly.")

    print("\nVerification Complete.")

if __name__ == "__main__":
    run_verification()
