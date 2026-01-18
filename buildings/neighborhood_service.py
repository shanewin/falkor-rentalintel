import logging
import random
from decimal import Decimal
from django.utils import timezone
from .models import Building, NearbySchool

logger = logging.getLogger(__name__)

class NeighborhoodService:
    @staticmethod
    def update_building_data(building_id):
        """
        Gateway method to update all neighborhood data for a building.
        """
        try:
            building = Building.objects.get(id=building_id)
            
            # 1. Update Walk Scores
            NeighborhoodService._update_walk_scores(building)
            
            # 2. Update Nearby Schools
            NeighborhoodService._update_nearby_schools(building)
            
            # 3. Mark as updated
            building.neighborhood_data_updated = timezone.now()
            building.save()
            
            return True
        except Exception as e:
            logger.error(f"Error updating neighborhood data for building {building_id}: {e}")
            return False

    @staticmethod
    def _update_walk_scores(building):
        """
        Fetches scores from Walk Score API.
        MOCK IMPLEMENTATION for now.
        """
        # In a real implementation, we would call the Walk Score API here.
        # For now, generate deterministic mock scores based on ID
        seed = building.id
        random.seed(seed)
        
        building.walk_score = random.randint(60, 95)
        building.bike_score = random.randint(40, 90)
        building.transit_score = random.randint(50, 98)
        
        # Descriptions based on standard Walk Score ranges
        if building.walk_score >= 90:
            building.walk_description = "Walker's Paradise"
        elif building.walk_score >= 70:
            building.walk_description = "Very Walkable"
        else:
            building.walk_description = "Somewhat Walkable"
            
        if building.bike_score >= 90:
            building.bike_description = "Biker's Paradise"
        elif building.bike_score >= 70:
            building.bike_description = "Very Bikeable"
        else:
            building.bike_description = "Somewhat Bikeable"
            
        building.transit_description = "Excellent Transit" if building.transit_score > 80 else "Good Transit"
        building.save()

    @staticmethod
    def _update_nearby_schools(building):
        """
        Fetches schools from GreatSchools API.
        MOCK IMPLEMENTATION for now.
        """
        # Clear existing schools to refresh
        building.nearby_schools.all().delete()
        
        # Mock schools data
        mock_schools = [
            {"name": f"P.S. {random.randint(1, 100)} {building.neighborhood or 'Local'}", "rating": random.randint(6, 10), "grades": "PK-5", "distance": Decimal(str(round(random.uniform(0.1, 0.8), 1))), "type": "Public"},
            {"name": f"I.S. {random.randint(1, 100)} Bernstein", "rating": random.randint(5, 9), "grades": "6-8", "distance": Decimal(str(round(random.uniform(1.0, 2.0), 1))), "type": "Public"},
            {"name": f"{building.neighborhood or 'Local'} High School", "rating": random.randint(7, 10), "grades": "9-12", "distance": Decimal(str(round(random.uniform(1.5, 3.0), 1))), "type": "Public"},
        ]
        
        for school in mock_schools:
            NearbySchool.objects.create(
                building=building,
                name=school["name"],
                rating=school["rating"],
                grades=school["grades"],
                distance=school["distance"],
                school_type=school["type"]
            )
