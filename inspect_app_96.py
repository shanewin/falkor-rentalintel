import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'doorway.settings')
django.setup()

from applications.models import Application
from apartments.models import Apartment, ApartmentImage
from buildings.models import Building, BuildingImage

def inspect_application(app_id):
    try:
        app = Application.objects.get(id=app_id)
        print(f"Application ID: {app.id}")
        print(f"Status: {app.status}")
        
        if app.apartment:
            apt = app.apartment
            print(f"Apartment: {apt.unit_number} in {apt.building.name}")
            
            apt_images = apt.images.all()
            print(f"Apartment Images: {apt_images.count()}")
            for img in apt_images:
                try:
                    print(f"  - Large URL: {img.large_url()}")
                except Exception as e:
                    print(f"  - Large URL Error: {e}")
            
            bldg = apt.building
            bldg_images = bldg.images.all()
            print(f"Building Images: {bldg_images.count()}")
            for img in bldg_images:
                try:
                    print(f"  - Large URL: {img.large_url()}")
                except Exception as e:
                    print(f"  - Large URL Error: {e}")
        else:
            print("No apartment associated with this application.")
            
    except Application.DoesNotExist:
        print(f"Application {app_id} does not exist.")

if __name__ == "__main__":
    inspect_application(96)
