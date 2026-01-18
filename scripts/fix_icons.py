import os
import django
import sys

# Setup Django environment
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doorway.settings')
django.setup()

from buildings.models import Amenity
from apartments.models import ApartmentAmenity

def update_icons():
    # Update Building Amenities
    b_updates = {
        "Children's Play Room": "fa-child",
        "Laundry": "fa-soap",
        "Laundry In Building": "fa-soap",
    }
    
    print("Updating Building Amenities...")
    for name, icon in b_updates.items():
        count = Amenity.objects.filter(name__iexact=name).update(icon=icon)
        print(f"Updated {name} to {icon}: {count}")

    # Update Apartment Amenities
    a_updates = {
        "Stainless Steel Appliances": "fa-blender",  # Safer than kitchen-set
        "Updated Kitchen": "fa-fire",         # Safer than fire-burner
    }
    
    print("\nUpdating Apartment Amenities...")
    for name, icon in a_updates.items():
        count = ApartmentAmenity.objects.filter(name__iexact=name).update(icon=icon)
        print(f"Updated {name} to {icon}: {count}")

if __name__ == "__main__":
    update_icons()
