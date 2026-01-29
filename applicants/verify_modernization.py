import os
import django
import sys
from decimal import Decimal

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate.settings')
django.setup()

from applicants.models import Applicant
from applicants.smart_insights import SmartInsights

def verify():
    print("--- Verifying Modernized SmartInsights & Profile Logic ---")
    
    # 1. Test get_field_completion_status for 'steps' and 'missing_details'
    print("\n1. Testing get_field_completion_status modernized format...")
    applicant = Applicant.objects.first()
    if not applicant:
        print("❌ No applicant found in DB to test with.")
        return
    
    status = applicant.get_field_completion_status()
    steps = status.get('steps', {})
    
    if steps:
        print(f"✅ 'steps' key found with {len(steps)} steps.")
        for step_num, step_data in steps.items():
            name = step_data.get('name')
            missing_details = step_data.get('missing_details', [])
            print(f"   Step {step_num}: {name} ({len(missing_details)} missing items)")
            if not name:
                print(f"   ❌ Step {step_num} is missing a name!")
            if not isinstance(missing_details, list):
                print(f"   ❌ Step {step_num} missing_details is not a list!")
    else:
        print("❌ 'steps' key NOT found in completion status.")

    # 2. Test SmartInsights.analyze_applicant execution (now using steps)
    print("\n2. Testing SmartInsights.analyze_applicant performance (Modernized)...")
    try:
        insights = SmartInsights.analyze_applicant(applicant)
        print(f"✅ analyze_applicant executed successfully for applicant: {applicant}")
        print(f"   Overall Score: {insights['overall_score']}")
        
        # Check if missing requirements are categorized correctly
        for cat, fields in insights.get('missing_requirements', {}).items():
            print(f"   Group '{cat}': {fields}")
            
    except KeyError as e:
        print(f"❌ KeyError caught: {e}")
    except Exception as e:
        print(f"❌ An error occurred: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    verify()
