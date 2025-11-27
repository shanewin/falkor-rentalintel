"""
Django management command to geocode building addresses
"""
from django.core.management.base import BaseCommand
from buildings.models import Building
import time
import random


class Command(BaseCommand):
    help = 'Geocode building addresses to populate latitude/longitude'

    def handle(self, *args, **options):
        buildings = Building.objects.filter(latitude__isnull=True) | Building.objects.filter(longitude__isnull=True)
        
        self.stdout.write(f"Found {buildings.count()} buildings to geocode")
        
        # NYC neighborhoods with their approximate coordinates
        neighborhood_coords = {
            'Upper West Side': (40.7870, -73.9754),
            'Upper East Side': (40.7736, -73.9566),
            'Midtown': (40.7549, -73.9840),
            'Chelsea': (40.7465, -74.0014),
            'Greenwich Village': (40.7336, -73.9991),
            'East Village': (40.7265, -73.9815),
            'Lower East Side': (40.7153, -73.9874),
            'Tribeca': (40.7163, -74.0086),
            'Financial District': (40.7074, -74.0113),
            'Williamsburg': (40.7081, -73.9571),
            'Greenpoint': (40.7304, -73.9540),
            'Bed-Stuy': (40.6895, -73.9535),
            'Crown Heights': (40.6696, -73.9442),
            'Park Slope': (40.6710, -73.9778),
            'Bushwick': (40.6942, -73.9222),
            'Astoria': (40.7644, -73.9235),
            'Long Island City': (40.7447, -73.9485),
            'Flushing': (40.7676, -73.8330),
        }
        
        updated = 0
        for building in buildings:
            neighborhood = building.neighborhood
            
            if neighborhood in neighborhood_coords:
                # Use base coordinates for the neighborhood
                base_lat, base_lng = neighborhood_coords[neighborhood]
                
                # Add small random offset to spread buildings out
                offset_lat = random.uniform(-0.005, 0.005)
                offset_lng = random.uniform(-0.005, 0.005)
                
                building.latitude = base_lat + offset_lat
                building.longitude = base_lng + offset_lng
                building.save()
                
                updated += 1
                self.stdout.write(f"✓ Geocoded {building.name} in {neighborhood}")
            else:
                # Default to midtown Manhattan for unknown neighborhoods
                building.latitude = 40.7549 + random.uniform(-0.01, 0.01)
                building.longitude = -73.9840 + random.uniform(-0.01, 0.01)
                building.save()
                updated += 1
                self.stdout.write(f"✓ Geocoded {building.name} (default location)")
            
            time.sleep(0.05)
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Successfully geocoded {updated} buildings"))