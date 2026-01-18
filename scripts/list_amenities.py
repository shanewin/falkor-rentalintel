import os
import django
import sys

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doorway.settings')
django.setup()

from buildings.models import Amenity as BuildingAmenity
from apartments.models import ApartmentAmenity

def list_amenities():
    print("--- BUILDING AMENITIES ---")
    for a in BuildingAmenity.objects.all().order_by('name'):
        print(f"{a.name}")

    print("\n--- APARTMENT FEATURES ---")
    for a in ApartmentAmenity.objects.all().order_by('name'):
        print(f"{a.name}")

if __name__ == "__main__":
    list_amenities()
