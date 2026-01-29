import os
import django
import sys

# Setup Django environment
sys.path.append('/Users/shanewinter/Desktop/door-way')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate.settings')
django.setup()

from applicants.models import Applicant

def analyze_applicant(email):
    try:
        applicant = Applicant.objects.get(email=email)
        status = applicant.get_field_completion_status()
        
        print(f"--- Analysis for {email} ---")
        print(f"Overall Completion: {status['overall_completion_percentage']}%")
        print("\nStep Breakdown:")
        for step_num, step_data in status['steps'].items():
            print(f"Step {step_num} ({step_data['name']}): {step_data['pct']}%")
            if step_data['missing']:
                print(f"  Missing: {', '.join(step_data['missing'])}")
        
        print("\n--- Model Fields ---")
        fields = [
            'first_name', 'last_name', 'email', 'phone_number', 'date_of_birth',
            'street_address_1', 'city', 'state', 'zip_code', 'housing_status',
            'evicted_before', 'reason_for_moving', 'employment_status',
            'annual_income', 'company_name', 'position'
        ]
        for f in fields:
            val = getattr(applicant, f, 'N/A')
            print(f"{f}: {val}")
            
        print(f"\nPhotos count: {applicant.photos.count()}")
        print(f"Prev addresses count: {applicant.previous_addresses.count()}")
        print(f"ID docs count: {applicant.identification_documents.count()}")
        print(f"Pets count: {applicant.pets.count()}")
        print(f"Neighborhoods count: {applicant.neighborhood_preferences.count()}")
        print(f"Amenities count: {applicant.amenities.count()}")
        
    except Applicant.DoesNotExist:
        print(f"Applicant with email {email} not found.")

if __name__ == "__main__":
    analyze_applicant('applicant_46_erica@example.com')
