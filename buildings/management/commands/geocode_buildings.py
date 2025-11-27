"""
Management command to geocode building addresses and populate latitude/longitude fields.
Uses Nominatim (OpenStreetMap) geocoding service - free and no API key required.
"""

from django.core.management.base import BaseCommand
from buildings.models import Building
import time
import requests
from decimal import Decimal


class Command(BaseCommand):
    help = 'Geocode building addresses to populate latitude and longitude fields'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-geocoding of buildings that already have coordinates',
        )
        parser.add_argument(
            '--building-id',
            type=int,
            help='Geocode a specific building by ID',
        )
    
    def geocode_address(self, address):
        """
        Geocode an address using Nominatim (OpenStreetMap) API.
        Returns (latitude, longitude) tuple or (None, None) if failed.
        """
        try:
            # Nominatim API endpoint (free, no key required)
            url = "https://nominatim.openstreetmap.org/search"
            
            # Add headers to identify our application (required by Nominatim)
            headers = {
                'User-Agent': 'DoorwayRentalApp/1.0'
            }
            
            params = {
                'q': address,
                'format': 'json',
                'limit': 1,
                'countrycodes': 'us'  # Limit to US addresses
            }
            
            response = requests.get(url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data and len(data) > 0:
                result = data[0]
                lat = Decimal(result['lat'])
                lon = Decimal(result['lon'])
                return lat, lon
            else:
                self.stdout.write(self.style.WARNING(f'No results found for: {address}'))
                return None, None
                
        except requests.exceptions.RequestException as e:
            self.stdout.write(self.style.ERROR(f'Geocoding error: {e}'))
            return None, None
        except (KeyError, ValueError) as e:
            self.stdout.write(self.style.ERROR(f'Error parsing response: {e}'))
            return None, None
    
    def handle(self, *args, **options):
        force_update = options.get('force', False)
        building_id = options.get('building_id')
        
        # Get buildings to geocode
        if building_id:
            buildings = Building.objects.filter(id=building_id)
            if not buildings.exists():
                self.stdout.write(self.style.ERROR(f'Building with ID {building_id} not found'))
                return
        else:
            if force_update:
                buildings = Building.objects.all()
            else:
                buildings = Building.objects.filter(latitude__isnull=True, longitude__isnull=True)
        
        total = buildings.count()
        
        if total == 0:
            self.stdout.write(self.style.SUCCESS('No buildings need geocoding'))
            return
        
        self.stdout.write(f'Found {total} buildings to geocode')
        
        success_count = 0
        failed_count = 0
        
        for i, building in enumerate(buildings, 1):
            # Construct full address
            address_parts = [
                building.street_address_1,
                building.street_address_2 if building.street_address_2 else None,
                building.city,
                building.get_state_display(),
                building.zip_code
            ]
            # Filter out None values and join
            full_address = ', '.join(filter(None, address_parts))
            
            self.stdout.write(f'[{i}/{total}] Geocoding: {building.name}')
            self.stdout.write(f'  Address: {full_address}')
            
            # Geocode the address
            lat, lon = self.geocode_address(full_address)
            
            if lat and lon:
                building.latitude = lat
                building.longitude = lon
                building.save()
                self.stdout.write(self.style.SUCCESS(f'  ✓ Saved coordinates: {lat}, {lon}'))
                success_count += 1
            else:
                # Try with just street, city, state if full address fails
                fallback_address = f"{building.street_address_1}, {building.city}, {building.get_state_display()}"
                self.stdout.write(f'  Trying fallback address: {fallback_address}')
                lat, lon = self.geocode_address(fallback_address)
                
                if lat and lon:
                    building.latitude = lat
                    building.longitude = lon
                    building.save()
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Saved coordinates: {lat}, {lon}'))
                    success_count += 1
                else:
                    self.stdout.write(self.style.ERROR(f'  ✗ Failed to geocode'))
                    failed_count += 1
            
            # Be respectful to the free API - wait 1 second between requests
            if i < total:
                time.sleep(1)
        
        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'Successfully geocoded: {success_count} buildings'))
        if failed_count > 0:
            self.stdout.write(self.style.WARNING(f'Failed to geocode: {failed_count} buildings'))
        self.stdout.write('='*50)