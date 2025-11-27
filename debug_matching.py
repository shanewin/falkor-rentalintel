# debug_matching.py
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate.settings')
django.setup()

from applicants.models import Applicant
from apartments.models import Apartment
from applicants.apartment_matching import ApartmentMatchingService, get_apartment_matches_for_applicant

def debug_matching():
    applicant = Applicant.objects.get(email='saffowovoinne-2296@yopmail.com')
    apt = Apartment.objects.first()
    
    print("=== APPLICANT INFO ===")
    print(f"Name: {applicant.first_name} {applicant.last_name}")
    print(f"Budget: ${applicant.max_rent_budget}")
    print(f"Min Bedrooms: {applicant.min_bedrooms}")
    print(f"Max Bedrooms: {applicant.max_bedrooms}")
    
    print("\n=== APARTMENT INFO ===")
    print(f"Unit: {apt.unit_number}")
    print(f"Rent: ${apt.rent_price}")
    print(f"Bedrooms: {apt.bedrooms}")
    print(f"Status: {apt.status}")
    print(f"Building: {apt.building}")
    print(f"Neighborhood: {apt.building.neighborhood if apt.building else 'N/A'}")
    
    print("\n=== NEIGHBORHOOD PREFERENCES ===")
    from applicants.models import NeighborhoodPreference
    neighborhood_prefs = NeighborhoodPreference.objects.filter(applicant=applicant)
    if neighborhood_prefs.exists():
        for pref in neighborhood_prefs:
            print(f"  #{pref.preference_rank}: {pref.neighborhood.name}")
    else:
        print("  No neighborhood preferences set")
    
    print("\n=== RUNNING MATCHING SERVICE ===")
    try:
        # Test the matching service
        matches = get_apartment_matches_for_applicant(applicant, limit=10)
        
        print(f"Matches found: {len(matches)}")
        
        if matches:
            for i, match in enumerate(matches, 1):
                print(f"\n--- Match #{i} ---")
                print(f"  Unit: {match['apartment'].unit_number}")
                print(f"  Rent: ${match['apartment'].rent_price}")
                print(f"  Match %: {match['match_percentage']}%")
                print(f"  Match Level: {match['match_details']['match_level']}")
                
                if match['match_details']['basic_reasons']:
                    print(f"  Concerns: {match['match_details']['basic_reasons']}")
                if match['match_details']['basic_positives']:
                    print(f"  Positives: {match['match_details']['basic_positives'][:2]}")
        else:
            print("\n⚠️ NO MATCHES FOUND!")
            print("\nDebugging why no matches...")
            
            # Check if apartment would pass basic filters
            service = ApartmentMatchingService(applicant)
            
            print("\n--- Checking Basic Filters ---")
            print(f"Apartment status: {apt.status} (needs 'available')")
            
            if apt.building:
                print(f"Apartment neighborhood: {apt.building.neighborhood}")
                neighborhood_names = [p.neighborhood.name for p in neighborhood_prefs]
                print(f"Preferred neighborhoods: {neighborhood_names}")
                
                if neighborhood_prefs.exists():
                    in_preferred = apt.building.neighborhood in neighborhood_names
                    print(f"Is in preferred neighborhood? {in_preferred}")
            
            print(f"\nApplicant budget: ${applicant.max_rent_budget}")
            print(f"Apartment rent: ${apt.rent_price}")
            budget_with_tolerance = applicant.max_rent_budget * 1.10
            print(f"Within budget + 10% tolerance? {apt.rent_price <= budget_with_tolerance}")
            
            print(f"\nApplicant bedrooms: {applicant.min_bedrooms} - {applicant.max_bedrooms}")
            print(f"Apartment bedrooms: {apt.bedrooms}")
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    debug_matching()