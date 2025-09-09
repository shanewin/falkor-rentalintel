"""
Apartment Matching Algorithm
============================

This module provides sophisticated apartment matching functionality based on applicant preferences.
Uses weighted scoring across multiple factors to calculate match percentages.

Scoring Factors:
1. Basic Requirements (60% weight)
   - Bedrooms/Bathrooms fit
   - Price range (with tolerance)
   - Neighborhood preferences (ranked)
   
2. Building Amenities (25% weight)
   - Must Have: Full points if present, major penalty if missing
   - Important: Good points if present, minor penalty if missing  
   - Nice to Have: Bonus points if present, no penalty if missing
   - Don't Care: No impact
   
3. Apartment Amenities (15% weight)
   - Same scoring system as building amenities
"""

from django.db.models import Q, Prefetch
from decimal import Decimal
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class ApartmentMatchingService:
    """
    Service class for matching apartments to applicant preferences using weighted scoring.
    """
    
    # Scoring weights for different factors
    BASIC_REQUIREMENTS_WEIGHT = 0.60
    BUILDING_AMENITIES_WEIGHT = 0.25  
    APARTMENT_AMENITIES_WEIGHT = 0.15
    
    # Priority level point values
    AMENITY_POINTS = {
        4: {'present': 100, 'missing': -50},  # Must Have
        3: {'present': 75, 'missing': -15},   # Important  
        2: {'present': 25, 'missing': 0},     # Nice to Have
        1: {'present': 0, 'missing': 0},      # Don't Care
    }
    
    def __init__(self, applicant):
        """Initialize with applicant instance"""
        self.applicant = applicant
        self.logger = logging.getLogger(f"{__name__}.{applicant.id}")
        
    def get_apartment_matches(self, limit: int = 20) -> List[Dict]:
        """
        Get apartments ranked by match percentage for this applicant.
        
        Args:
            limit: Maximum number of apartments to return
            
        Returns:
            List of dictionaries with apartment and match_percentage
        """
        from apartments.models import Apartment
        
        # Get available apartments with related data
        apartments = Apartment.objects.filter(
            status='available'
        ).select_related(
            'building'
        ).prefetch_related(
            'building__amenities',
            'amenities',
            'concessions',
            'images'
        )
        
        # Apply basic filters to reduce computation
        apartments = self._apply_basic_filters(apartments)
        
        matches = []
        for apartment in apartments:
            match_percentage = self._calculate_match_percentage(apartment)
            
            matches.append({
                'apartment': apartment,
                'match_percentage': match_percentage,
                'match_details': self._get_match_details(apartment, match_percentage)
            })
        
        # Sort by match percentage (highest first) and limit results
        matches.sort(key=lambda x: x['match_percentage'], reverse=True)
        
        # Always return at least some results - if no great matches, show best available
        if not matches:
            self.logger.warning(f"No apartment matches found for applicant {self.applicant.id}")
            return []
            
        return matches[:limit]
    
    def _apply_basic_filters(self, queryset):
        """Apply basic filters to reduce the apartment pool before detailed scoring"""
        
        # Neighborhood filter - only show apartments in preferred neighborhoods
        # Use the through model for ranked preferences
        from .models import NeighborhoodPreference
        neighborhood_preferences = NeighborhoodPreference.objects.filter(applicant=self.applicant)
        if neighborhood_preferences.exists():
            # Get list of preferred neighborhood names
            preferred_neighborhoods = [pref.neighborhood.name for pref in neighborhood_preferences]
            queryset = queryset.filter(building__neighborhood__in=preferred_neighborhoods)
        
        # Bedroom filter - allow some flexibility 
        if self.applicant.min_bedrooms or self.applicant.max_bedrooms:
            bedroom_filter = Q()
            
            if self.applicant.min_bedrooms:
                # Handle "studio" as 0 bedrooms
                if isinstance(self.applicant.min_bedrooms, str) and self.applicant.min_bedrooms.lower() == 'studio':
                    min_beds = 0
                else:
                    try:
                        min_beds = max(0, float(self.applicant.min_bedrooms) - 0.5)
                    except (ValueError, TypeError):
                        min_beds = 0
                bedroom_filter &= Q(bedrooms__gte=min_beds)
                
            if self.applicant.max_bedrooms:
                # Handle max bedrooms conversion
                if isinstance(self.applicant.max_bedrooms, str):
                    try:
                        max_beds = float(self.applicant.max_bedrooms) + 0.5
                    except (ValueError, TypeError):
                        max_beds = 1.5  # Default to 1BR + flexibility
                else:
                    max_beds = self.applicant.max_bedrooms + 0.5
                bedroom_filter &= Q(bedrooms__lte=max_beds)
                
            queryset = queryset.filter(bedroom_filter)
        
        # Rent filter - allow 10% over budget for "good matches"
        if self.applicant.max_rent_budget:
            max_rent_with_tolerance = self.applicant.max_rent_budget * Decimal('1.10')
            queryset = queryset.filter(rent_price__lte=max_rent_with_tolerance)
        
        return queryset
    
    def _calculate_match_percentage(self, apartment) -> int:
        """
        Calculate overall match percentage for an apartment.
        
        Returns:
            Integer percentage (0-100)
        """
        
        # Calculate scores for each category
        basic_score = self._calculate_basic_requirements_score(apartment)
        building_amenities_score = self._calculate_building_amenities_score(apartment)
        apartment_amenities_score = self._calculate_apartment_amenities_score(apartment)
        
        # Apply weights and calculate final percentage
        weighted_score = (
            basic_score * self.BASIC_REQUIREMENTS_WEIGHT +
            building_amenities_score * self.BUILDING_AMENITIES_WEIGHT +
            apartment_amenities_score * self.APARTMENT_AMENITIES_WEIGHT
        )
        
        # Ensure percentage is between 0-100
        return max(0, min(100, int(weighted_score)))
    
    def _calculate_basic_requirements_score(self, apartment) -> float:
        """Calculate score based on basic requirements (bedrooms, bathrooms, rent, neighborhood, pets)"""
        
        score = 100.0  # Start with perfect score
        
        # Bedroom scoring
        if self.applicant.min_bedrooms or self.applicant.max_bedrooms:
            bedroom_score = self._score_bedroom_match(apartment)
            score = score * (bedroom_score / 100.0)
        
        # Bathroom scoring  
        if self.applicant.min_bathrooms or self.applicant.max_bathrooms:
            bathroom_score = self._score_bathroom_match(apartment)
            score = score * (bathroom_score / 100.0)
            
        # Rent scoring
        if self.applicant.max_rent_budget:
            rent_score = self._score_rent_match(apartment)
            score = score * (rent_score / 100.0)
            
        # Neighborhood preference scoring (ranked)
        neighborhood_score = self._score_neighborhood_match(apartment)
        score = score * (neighborhood_score / 100.0)
        
        # Pet policy scoring
        pet_score = self._score_pet_policy_match(apartment)
        score = score * (pet_score / 100.0)
        
        return score
    
    def _score_bedroom_match(self, apartment) -> float:
        """Score how well apartment bedrooms match preferences"""
        
        apt_bedrooms = float(apartment.bedrooms or 0)
        
        # Convert string preferences to numeric
        min_beds = self._convert_bedroom_preference(self.applicant.min_bedrooms)
        max_beds = self._convert_bedroom_preference(self.applicant.max_bedrooms)
        
        # Perfect match
        if min_beds is not None and max_beds is not None:
            if min_beds <= apt_bedrooms <= max_beds:
                return 100.0
                
        # Check individual bounds
        if min_beds is not None and apt_bedrooms < min_beds:
            # Slight penalty for fewer bedrooms than wanted
            if apt_bedrooms >= min_beds - 0.5:
                return 85.0  # Studio when 1BR wanted
            else:
                return 60.0  # Significantly fewer bedrooms
                
        if max_beds is not None and apt_bedrooms > max_beds:
            # Minor penalty for more bedrooms (might be more expensive)
            return 90.0
            
        return 100.0
    
    def _convert_bedroom_preference(self, bedroom_pref) -> float:
        """Convert bedroom preference to numeric value"""
        if bedroom_pref is None:
            return None
        if isinstance(bedroom_pref, str):
            if bedroom_pref.lower() == 'studio':
                return 0.0
            try:
                return float(bedroom_pref)
            except (ValueError, TypeError):
                return None
        try:
            return float(bedroom_pref)
        except (ValueError, TypeError):
            return None
    
    def _score_bathroom_match(self, apartment) -> float:
        """Score how well apartment bathrooms match preferences"""
        
        apt_bathrooms = float(apartment.bathrooms or 1.0)
        
        # Convert bathroom preferences to numeric
        min_baths = self._convert_numeric_preference(self.applicant.min_bathrooms)
        max_baths = self._convert_numeric_preference(self.applicant.max_bathrooms)
        
        # Perfect match
        if min_baths is not None and max_baths is not None:
            if min_baths <= apt_bathrooms <= max_baths:
                return 100.0
                
        # Check individual bounds with tolerance
        if min_baths is not None and apt_bathrooms < min_baths:
            return 75.0  # Minor penalty for fewer bathrooms
            
        if max_baths is not None and apt_bathrooms > max_baths:
            return 95.0  # Very minor penalty for extra bathrooms
            
        return 100.0
    
    def _convert_numeric_preference(self, value):
        """Convert preference value to numeric"""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _score_rent_match(self, apartment) -> float:
        """Score how well apartment rent matches budget with tolerance"""
        
        if not self.applicant.max_rent_budget:
            return 100.0
            
        rent = apartment.rent_price
        budget = self.applicant.max_rent_budget
        
        if rent <= budget:
            return 100.0  # Within budget - perfect
            
        # Calculate overage percentage
        overage_percent = ((rent - budget) / budget) * 100
        
        if overage_percent <= 3:  # Up to 3% over budget  
            return 90.0
        elif overage_percent <= 6:  # Up to 6% over budget
            return 75.0
        elif overage_percent <= 10:  # Up to 10% over budget (our filter limit)
            return 50.0
        else:
            return 0.0  # Should not happen due to filtering
    
    def _score_neighborhood_match(self, apartment) -> float:
        """Score based on ranked neighborhood preferences"""
        
        # Get user's neighborhood preferences with rankings using through model
        from .models import NeighborhoodPreference
        neighborhood_prefs = NeighborhoodPreference.objects.filter(
            applicant=self.applicant
        ).select_related('neighborhood')
        
        if not neighborhood_prefs.exists():
            return 100.0  # No preference = all neighborhoods are fine
            
        apartment_neighborhood = apartment.building.neighborhood
        
        # Find the preference rank for this neighborhood
        for pref in neighborhood_prefs:
            if pref.neighborhood.name == apartment_neighborhood:
                # Score based on ranking (1st choice = 100%, 2nd = 90%, etc.)
                rank = pref.preference_rank
                if rank == 1:
                    return 100.0
                elif rank == 2:
                    return 90.0
                elif rank == 3:
                    return 80.0
                elif rank == 4:
                    return 70.0
                else:
                    return max(50.0, 100.0 - (rank * 10))
        
        # Neighborhood not in preferences - should be filtered out, but just in case
        return 30.0
    
    def _calculate_building_amenities_score(self, apartment) -> float:
        """Calculate score based on building amenity preferences"""
        
        # Get user's building amenity preferences using the correct relationship name
        building_prefs = self.applicant.building_amenity_preferences.select_related('amenity').all()
        
        if not building_prefs.exists():
            return 100.0  # No preferences = no penalties
            
        # Get apartment's building amenities
        building_amenities = set(apartment.building.amenities.values_list('id', flat=True))
        
        total_points = 0
        max_possible_points = 0
        
        for pref in building_prefs:
            amenity_id = pref.amenity.id
            priority_level = pref.priority_level
            
            points_config = self.AMENITY_POINTS[priority_level]
            
            if amenity_id in building_amenities:
                total_points += points_config['present']
            else:
                total_points += points_config['missing']
                
            # Max possible assumes all amenities are present
            max_possible_points += points_config['present']
        
        if max_possible_points == 0:
            return 100.0
            
        # Convert to percentage, ensuring non-negative
        percentage = max(0, (total_points / max_possible_points) * 100)
        return min(100.0, percentage)
    
    def _calculate_apartment_amenities_score(self, apartment) -> float:
        """Calculate score based on apartment amenity preferences"""
        
        # Get user's apartment amenity preferences using the correct relationship name  
        apartment_prefs = self.applicant.apartment_amenity_preferences.select_related('amenity').all()
        
        if not apartment_prefs.exists():
            return 100.0  # No preferences = no penalties
            
        # Get apartment amenities
        apartment_amenities = set(apartment.amenities.values_list('id', flat=True))
        
        total_points = 0
        max_possible_points = 0
        
        for pref in apartment_prefs:
            amenity_id = pref.amenity.id  
            priority_level = pref.priority_level
            
            points_config = self.AMENITY_POINTS[priority_level]
            
            if amenity_id in apartment_amenities:
                total_points += points_config['present']
            else:
                total_points += points_config['missing']
                
            # Max possible assumes all amenities are present
            max_possible_points += points_config['present']
        
        if max_possible_points == 0:
            return 100.0
            
        # Convert to percentage, ensuring non-negative  
        percentage = max(0, (total_points / max_possible_points) * 100)
        return min(100.0, percentage)
    
    def _score_pet_policy_match(self, apartment) -> float:
        """Score how well the building's pet policy matches applicant's pet needs"""
        
        # Check if applicant has pets
        has_pets = self.applicant.pets.exists()
        
        if not has_pets:
            return 100.0  # No pets = no pet policy concerns
            
        # Get building's pet policy
        pet_policy = apartment.building.pet_policy
        
        # Score based on pet policy
        if pet_policy == 'all_pets':
            return 100.0  # Perfect - all pets allowed
        elif pet_policy == 'small_pets':
            # Check if user's pets are small (under 25 lbs typically)
            pets = self.applicant.pets.all()
            all_small = True
            for pet in pets:
                # Check if pet has weight info and is over 25 lbs
                if hasattr(pet, 'description') and pet.description:
                    # Try to extract weight from description
                    import re
                    weight_match = re.search(r'(\d+)\s*pounds?|(\d+)\s*lbs?', pet.description.lower())
                    if weight_match:
                        weight = int(weight_match.group(1) or weight_match.group(2))
                        if weight > 25:
                            all_small = False
                            break
            return 90.0 if all_small else 60.0
        elif pet_policy == 'cats_only':
            # Check if all pets are cats
            pets = self.applicant.pets.all()
            all_cats = all(
                hasattr(pet, 'pet_type') and 'cat' in pet.pet_type.lower() 
                for pet in pets
            )
            return 95.0 if all_cats else 30.0
        elif pet_policy == 'case_by_case':
            return 70.0  # Moderate score - not guaranteed but possible
        elif pet_policy == 'pet_fee':
            return 85.0  # Good score - allowed with fee
        elif pet_policy == 'no_pets':
            return 20.0  # Very low score - pets not allowed
        else:
            return 70.0  # Unknown policy - assume case by case
    
    def _get_match_details(self, apartment, match_percentage: int) -> Dict:
        """Get detailed breakdown of why this apartment matched"""
        
        basic_score = self._calculate_basic_requirements_score(apartment)
        building_score = self._calculate_building_amenities_score(apartment)  
        apartment_score = self._calculate_apartment_amenities_score(apartment)
        
        # Determine match level
        if match_percentage >= 90:
            match_level = "Excellent Match"
            match_color = "success"
        elif match_percentage >= 75:
            match_level = "Great Match"
            match_color = "primary"
        elif match_percentage >= 60:
            match_level = "Good Match" 
            match_color = "info"
        else:
            match_level = "Fair Match"
            match_color = "warning"
            
        return {
            'match_level': match_level,
            'match_color': match_color,
            'basic_score': round(basic_score, 1),
            'building_amenities_score': round(building_score, 1),
            'apartment_amenities_score': round(apartment_score, 1),
            'rent_within_budget': apartment.rent_price <= (self.applicant.max_rent_budget or apartment.rent_price),
            'preferred_neighborhood': self._is_preferred_neighborhood(apartment),
        }
    
    def _is_preferred_neighborhood(self, apartment) -> bool:
        """Check if apartment is in a preferred neighborhood"""
        from .models import NeighborhoodPreference
        preferred_neighborhoods = NeighborhoodPreference.objects.filter(
            applicant=self.applicant
        ).values_list('neighborhood__name', flat=True)
        return apartment.building.neighborhood in preferred_neighborhoods


# Utility function for easy access
def get_apartment_matches_for_applicant(applicant, limit: int = 20) -> List[Dict]:
    """
    Convenience function to get apartment matches for an applicant.
    
    Args:
        applicant: Applicant instance
        limit: Maximum number of results to return
        
    Returns:
        List of apartment match dictionaries
    """
    service = ApartmentMatchingService(applicant)
    return service.get_apartment_matches(limit)