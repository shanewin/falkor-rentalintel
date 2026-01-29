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
    print("--- Verifying SmartInsights Fix ---")
    
    # 1. Test get_field_completion_status for 'sections' key
    print("\n1. Testing get_field_completion_status format...")
    applicant = Applicant.objects.first()
    if not applicant:
        print("❌ No applicant found in DB to test with.")
        return
    
    status = applicant.get_field_completion_status()
    if 'sections' in status:
        print("✅ 'sections' key found in completion status.")
        # Check for specific expected sections
        expected_sections = ['Basic Information', 'Current Address', 'Employment Information', 'Current Housing Details', 'Related Data']
        missing_sections = [s for s in expected_sections if s not in status['sections']]
        if not missing_sections:
            print("✅ All expected sections found.")
        else:
            print(f"❌ Missing sections: {missing_sections}")
    else:
        print("❌ 'sections' key NOT found in completion status.")

    # 2. Test SmartInsights.analyze_applicant execution
    print("\n2. Testing SmartInsights.analyze_applicant performance...")
    try:
        insights = SmartInsights.analyze_applicant(applicant)
        print(f"✅ analyze_applicant executed successfully for applicant: {applicant}")
        print(f"   Overall Score: {insights['overall_score']}")
        print(f"   Missing Requirements: {insights.get('missing_requirements', {}).keys()}")
    except KeyError as e:
        print(f"❌ KeyError caught: {e}")
    except Exception as e:
        print(f"❌ An error occurred: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    verify()
