import os
import django
from django.conf import settings

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate.settings')
django.setup()

from applicants.models import Applicant
from applications.models import Application
from buildings.models import BuildingImage
from apartments.models import ApartmentImage

def verify():
    print("--- Verifying Data Integrity ---")
    
    # 1. Check Nudge Candidates (missing income/budget)
    nudge_candidates = Applicant.objects.filter(annual_income__isnull=True, max_rent_budget__isnull=True).count()
    print(f"Nudge Candidates (missing income/budget): {nudge_candidates} (Expected: 30)")
    
    # 2. Check Application Satisfaction
    total_apps = Application.objects.count()
    satisfied_apps = 0
    unsatisfied_apps = 0
    for app in Application.objects.all():
        if app.is_satisfied():
            satisfied_apps += 1
        else:
            unsatisfied_apps += 1
            
    print(f"Total Applications: {total_apps}")
    print(f"Satisfied Applications: {satisfied_apps}")
    print(f"Unsatisfied Applications: {unsatisfied_apps}")
    
    # 3. Check Images
    b_images = BuildingImage.objects.count()
    a_images = ApartmentImage.objects.count()
    print(f"Building Images: {b_images} (Expected: 20)")
    print(f"Apartment Images: {a_images} (Expected: 100)")
    
    if nudge_candidates == 30 and b_images == 20 and a_images == 100:
        print("SUCCESS: Data verification passed!")
    else:
        print("FAILURE: Data verification failed!")

if __name__ == "__main__":
    verify()
