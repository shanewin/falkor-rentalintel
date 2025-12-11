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
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Tuple
import logging
import re

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
        """Initialize with applicant instance and cache preferences"""
        self.applicant = applicant
        self.logger = logging.getLogger(f"{__name__}.{applicant.id}")
        
        # CRITICAL FIX #4: Cache applicant preferences to avoid repeated DB queries
        self._cache_applicant_preferences()
    
    def _cache_applicant_preferences(self):
        """Cache applicant preferences to avoid repeated database queries"""
        try:
            # Cache neighborhood preferences with ranking
            from .models import NeighborhoodPreference
            self._neighborhood_prefs = list(
                NeighborhoodPreference.objects.filter(applicant=self.applicant)
                .select_related('neighborhood')
                .order_by('preference_rank')
            )
            
            # Cache building amenity preferences  
            self._building_amenity_prefs = list(
                self.applicant.building_amenity_preferences
                .select_related('amenity')
                .all()
            )
            
            # Cache apartment amenity preferences
            self._apartment_amenity_prefs = list(
                self.applicant.apartment_amenity_preferences
                .select_related('amenity') 
                .all()
            )
            
            # Cache pet information
            self._pets = list(self.applicant.pets.all())
            
        except Exception as e:
            # Fallback if caching fails
            self.logger.warning(f"Failed to cache preferences for applicant {self.applicant.id}: {e}")
            self._neighborhood_prefs = []
            self._building_amenity_prefs = []
            self._apartment_amenity_prefs = []
            self._pets = []
    
    def _get_cached_building_preferences(self):
        """Get cached building amenity preferences"""
        if not hasattr(self, '_building_amenity_prefs'):
            self._building_amenity_prefs = list(
                self.applicant.building_amenity_preferences
                .select_related('amenity')
                .all()
            )
        return self._building_amenity_prefs
    
    def _get_cached_apartment_preferences(self):
        """Get cached apartment amenity preferences"""
        if not hasattr(self, '_apartment_amenity_prefs'):
            self._apartment_amenity_prefs = list(
                self.applicant.apartment_amenity_preferences
                .select_related('amenity')
                .all()
            )
        return self._apartment_amenity_prefs
    
    def _get_cached_pets(self):
        """Get cached pet information as safe dictionaries"""
        if not hasattr(self, '_pets_cache'):
            self._pets_cache = []
            for pet in self._pets:
                try:
                    pet_data = {
                        'type': getattr(pet, 'pet_type', ''),
                        'weight': getattr(pet, 'weight', None),
                        'name': getattr(pet, 'name', ''),
                    }
                    self._pets_cache.append(pet_data)
                except Exception as e:
                    logger.warning(f"Error processing pet data for applicant {self.applicant.id}: {e}")
                    # Add safe fallback
                    self._pets_cache.append({
                        'type': 'unknown',
                        'weight': None,
                        'name': 'Pet',
                    })
        return self._pets_cache
        
    def get_apartment_matches(self, limit: int = 20) -> List[Dict]:
        """
        Get apartments ranked by match percentage for this applicant.
        
        Args:
            limit: Maximum number of apartments to return
            
        Returns:
            List of dictionaries with apartment and match_percentage
        """
        from apartments.models import Apartment
        
        # CRITICAL FIX #4: Optimize database queries to prevent N+1 problems
        apartments = Apartment.objects.filter(
            status='available'
        ).select_related(
            'building'
        ).prefetch_related(
            'building__amenities',
            'amenities', 
            'concessions',
            'images',
            # Prefetch related data used in scoring
            Prefetch('building__amenities', queryset=None),
            Prefetch('amenities', queryset=None)
        )

        # STRICT MATCHING GATING
        # If the user hasn't provided the "Must Have" fields, we return 0 matches.
        # This prevents the "100% Match" on empty profile bug.
        
        has_neighborhoods = bool(self._neighborhood_prefs)
        has_budget = self.applicant.max_rent_budget is not None and self.applicant.max_rent_budget > 0
        has_bedrooms = self.applicant.min_bedrooms is not None

        if not (has_neighborhoods and has_budget and has_bedrooms):
            self.logger.info(f"Applicant {self.applicant.id} missing core preferences (N:{has_neighborhoods}, $: {has_budget}, B:{has_bedrooms}). Returning 0 matches.")
            return []
        
        # End Strict Gating
        
        apartments = self._apply_basic_filters(apartments)
        
        matches = []
        for apartment in apartments:
            match_percentage = self._calculate_match_percentage(apartment)
            
            matches.append({
                'apartment': apartment,
                'match_percentage': match_percentage,
                'match_details': self._get_match_details(apartment, match_percentage)
            })
        
        matches.sort(key=lambda x: x['match_percentage'], reverse=True)
        
        # Always return at least some results - if no great matches, show best available
        if not matches:
            self.logger.warning(f"No apartment matches found for applicant {self.applicant.id}")
            return []
            
        return matches[:limit]
    
        return queryset

    def _apply_basic_filters(self, queryset):
        """Apply basic filters to reduce the apartment pool before detailed scoring"""
        
        # Neighborhood filter - only show apartments in preferred neighborhoods
        # Use cached preferences to avoid database queries
        if self._neighborhood_prefs:
            # User Feedback: "I might be inclined to live in a different neighborhood"
            # We relax the strict filter and rely on scoring to penalize non-matching neighborhoods
            pass
            # Get list of preferred neighborhood names from cache
            # preferred_neighborhoods = [pref.neighborhood.name for pref in self._neighborhood_prefs]
            # queryset = queryset.filter(building__neighborhood__in=preferred_neighborhoods)
        
        # Bedroom filter - allow some flexibility 
        if self.applicant.min_bedrooms or self.applicant.max_bedrooms:
            bedroom_filter = Q()
            
            if self.applicant.min_bedrooms:
                # Handle "studio" as 0 bedrooms
                if isinstance(self.applicant.min_bedrooms, str) and self.applicant.min_bedrooms.lower() == 'studio':
                    min_beds = Decimal('0')
                else:
                    try:
                        # CRITICAL FIX #1: Use Decimal arithmetic for precise bedroom calculations
                        min_beds_decimal = Decimal(str(self.applicant.min_bedrooms))
                        min_beds = max(Decimal('0'), min_beds_decimal - Decimal('0.5'))
                    except (ValueError, TypeError, InvalidOperation):
                        min_beds = Decimal('0')
                        logger.warning(f"Invalid min_bedrooms for applicant {self.applicant.id}: {self.applicant.min_bedrooms}")
                bedroom_filter &= Q(bedrooms__gte=float(min_beds))  # Django ORM needs float
                
            if self.applicant.max_bedrooms:
                # Handle max bedrooms conversion with Decimal precision
                try:
                    max_beds_decimal = Decimal(str(self.applicant.max_bedrooms))
                    max_beds = max_beds_decimal + Decimal('0.5')
                except (ValueError, TypeError, InvalidOperation):
                    max_beds = Decimal('1.5')  # Default to 1BR + flexibility
                    logger.warning(f"Invalid max_bedrooms for applicant {self.applicant.id}: {self.applicant.max_bedrooms}")
                bedroom_filter &= Q(bedrooms__lte=float(max_beds))  # Django ORM needs float
                
            queryset = queryset.filter(bedroom_filter)
        
        # Rent filter - allow 10% over budget for "good matches"
        if self.applicant.max_rent_budget:
            try:
                budget = Decimal(str(self.applicant.max_rent_budget))
                max_rent_with_tolerance = budget * Decimal('1.10')
                queryset = queryset.filter(rent_price__lte=max_rent_with_tolerance)
            except (InvalidOperation, ValueError):
                logger.warning(f"Invalid max_rent_budget for applicant {self.applicant.id}: {self.applicant.max_rent_budget}")
                # Skip rent filter if budget is invalid

        # STRICT PET FILTERING
        # "If you have a dog, and the building does not allow dogs, then the user cannot and will not live there."
        if self._pets:
            # 1. If user has ANY pets, exclude buildings that strictly forbid them
            queryset = queryset.exclude(building__pet_policy='no_pets')
            
            # 2. If user has a DOG (or other non-cat), exclude "Cats Only" buildings
            # We check the cached pets list for any non-cat type
            has_non_cats = any(
                'cat' not in str(pet.pet_type).lower() 
                for pet in self._pets
            )
            
            if has_non_cats:
                queryset = queryset.exclude(building__pet_policy='cats_only')
        
        # STRICT MOVE-IN DATE FILTERING
        # Exclude apartments that are not available by the desired move-in date
        if self.applicant.desired_move_in_date:
            # We filter out any apartment that has an availability date AFTER the desired move-in date.
            # This implies the unit is not ready when the user needs it.
            # Apartments with NO availability record are assumed Available Now (so they rely on status='available')
            queryset = queryset.exclude(
                availability_calendar__available_date__gt=self.applicant.desired_move_in_date
            )
        
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
        
        # CRITICAL FIX #1: Use Decimal for precise bedroom calculations
        try:
            apt_bedrooms = Decimal(str(apartment.bedrooms or 0))
        except (InvalidOperation, ValueError):
            apt_bedrooms = Decimal('0')
            logger.warning(f"Invalid bedrooms for apartment {apartment.id}: {apartment.bedrooms}")
        
        # Convert string preferences to numeric
        min_beds = self._convert_bedroom_preference(self.applicant.min_bedrooms)
        max_beds = self._convert_bedroom_preference(self.applicant.max_bedrooms)
        
        # Perfect match
        if min_beds is not None and max_beds is not None:
            if min_beds <= apt_bedrooms <= max_beds:
                return 100.0
                
        # Check individual bounds with Decimal precision
        if min_beds is not None and apt_bedrooms < min_beds:
            # Slight penalty for fewer bedrooms than wanted
            if apt_bedrooms >= min_beds - Decimal('0.5'):
                return 85.0  # Studio when 1BR wanted
            else:
                return 60.0  # Significantly fewer bedrooms
                
        if max_beds is not None and apt_bedrooms > max_beds:
            # Minor penalty for more bedrooms (might be more expensive)
            return 90.0
            
        return 100.0
    
    def _convert_bedroom_preference(self, bedroom_pref):
        """Convert bedroom preference to Decimal value for precision"""
        if bedroom_pref is None:
            return None
        if isinstance(bedroom_pref, str):
            if bedroom_pref.lower() == 'studio':
                return Decimal('0')
            try:
                return Decimal(bedroom_pref)
            except (ValueError, TypeError, InvalidOperation):
                return None
        try:
            return Decimal(str(bedroom_pref))
        except (ValueError, TypeError, InvalidOperation):
            return None
    
    def _score_bathroom_match(self, apartment) -> float:
        """Score how well apartment bathrooms match preferences"""
        
        # CRITICAL FIX #1: Use Decimal for precise bathroom calculations
        try:
            apt_bathrooms = Decimal(str(apartment.bathrooms or 1.0))
        except (InvalidOperation, ValueError):
            apt_bathrooms = Decimal('1.0')
            logger.warning(f"Invalid bathrooms for apartment {apartment.id}: {apartment.bathrooms}")
        
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
        """Convert preference value to Decimal for precision"""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError, InvalidOperation):
            return None
    
    def _score_rent_match(self, apartment) -> float:
        """Score how well apartment rent matches budget with tolerance"""
        
        if not self.applicant.max_rent_budget:
            return 100.0
        
        try:
            # CRITICAL FIX #1 & #2: Use Decimal arithmetic and protect against division by zero
            rent = Decimal(str(apartment.rent_price))
            budget = Decimal(str(self.applicant.max_rent_budget))
            
            if budget <= 0:
                logger.warning(f"Invalid budget for applicant {self.applicant.id}: {budget}")
                return 100.0  # No budget constraint
            
            if rent <= budget:
                return 100.0  # Within budget - perfect
                
            # Calculate overage percentage with safe division
            overage_percent = ((rent - budget) / budget) * Decimal('100')
            
            if overage_percent <= Decimal('3'):  # Up to 3% over budget  
                return 90.0
            elif overage_percent <= Decimal('6'):  # Up to 6% over budget
                return 75.0
            elif overage_percent <= Decimal('10'):  # Up to 10% over budget (our filter limit)
                return 50.0
            else:
                return 0.0  # Should not happen due to filtering
                
        except (InvalidOperation, ValueError, ZeroDivisionError) as e:
            logger.warning(f"Error calculating rent score for apartment {apartment.id}: {e}")
            return 100.0  # Default to no penalty if calculation fails
    
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
        return 40.0  # User Feedback: Non-match target ~63% total (40 * 0.6 + 40 amenity pts = 64)
    
    def _calculate_building_amenities_score(self, apartment) -> float:
        """Calculate score based on building amenity preferences"""
        
        # Use cached building amenity preferences
        if not self._building_amenity_prefs:
            return 100.0  # No preferences = no penalties
            
        # Get apartment's building amenities
        building_amenities = set(apartment.building.amenities.values_list('id', flat=True))
        
        total_points = 0
        max_possible_points = 0
        
        for pref in self._building_amenity_prefs:
            amenity_id = pref.amenity.id
            priority_level = pref.priority_level
            
            points_config = self.AMENITY_POINTS[priority_level]
            
            if amenity_id in building_amenities:
                total_points += points_config['present']
            else:
                total_points += points_config['missing']
                
            # Max possible assumes all amenities are present
            max_possible_points += points_config['present']
        
        # CRITICAL FIX #2: Division by zero protection
        if max_possible_points == 0:
            return 100.0
        
        try:
            # Convert to percentage, ensuring non-negative
            percentage = max(0, (total_points / max_possible_points) * 100)
            return min(100.0, percentage)
        except ZeroDivisionError:
            logger.warning(f"Division by zero in building amenities scoring for applicant {self.applicant.id}")
            return 100.0  # Default to perfect score if calculation fails
    
    def _calculate_apartment_amenities_score(self, apartment) -> float:
        """Calculate score based on apartment amenity preferences"""
        
        # Use cached apartment amenity preferences
        if not self._apartment_amenity_prefs:
            return 100.0  # No preferences = no penalties
            
        # Get apartment amenities
        apartment_amenities = set(apartment.amenities.values_list('id', flat=True))
        
        total_points = 0
        max_possible_points = 0
        
        for pref in self._apartment_amenity_prefs:
            amenity_id = pref.amenity.id  
            priority_level = pref.priority_level
            
            points_config = self.AMENITY_POINTS[priority_level]
            
            if amenity_id in apartment_amenities:
                total_points += points_config['present']
            else:
                total_points += points_config['missing']
                
            # Max possible assumes all amenities are present
            max_possible_points += points_config['present']
        
        # CRITICAL FIX #2: Division by zero protection
        if max_possible_points == 0:
            return 100.0
        
        try:
            # Convert to percentage, ensuring non-negative  
            percentage = max(0, (total_points / max_possible_points) * 100)
            return min(100.0, percentage)
        except ZeroDivisionError:
            logger.warning(f"Division by zero in apartment amenities scoring for applicant {self.applicant.id}")
            return 100.0  # Default to perfect score if calculation fails
    
    def _score_pet_policy_match(self, apartment) -> float:
        """Score how well the building's pet policy matches applicant's pet needs"""
        
        # Use cached pet information
        if not self._pets:
            return 100.0  # No pets = no pet policy concerns
            
        # Get building's pet policy
        pet_policy = apartment.building.pet_policy
        
        # Score based on pet policy
        if pet_policy == 'all_pets':
            return 100.0  # Perfect - all pets allowed
        elif pet_policy == 'small_pets':
            # Check if user's pets are small (under 25 lbs typically) using cached data
            all_small = True
            for pet in self._pets:
                # Safe pet weight parsing with validation
                if hasattr(pet, 'description') and pet.description:
                    try:
                        # Sanitize description and extract weight safely
                        description = str(pet.description).lower().strip()[:500]  # Limit length for security
                        weight_match = re.search(r'(\d{1,3})\s*(?:pounds?|lbs?)', description)
                        if weight_match:
                            weight_str = weight_match.group(1)
                            weight = int(weight_str)
                            # Validate reasonable weight range (1-300 lbs for pets)
                            if 1 <= weight <= 300 and weight > 25:
                                all_small = False
                                break
                    except (ValueError, AttributeError, re.error) as e:
                        logger.warning(f"Error parsing pet weight for applicant {self.applicant.id}, pet {pet.id}: {e}")
                        # Continue without weight info - assume large pet for safety
                        all_small = False
                        break
            return 90.0 if all_small else 60.0
        elif pet_policy == 'cats_only':
            # Check if all pets are cats using cached data
            all_cats = all(
                hasattr(pet, 'pet_type') and 'cat' in pet.pet_type.lower() 
                for pet in self._pets
            )
            return 95.0 if all_cats else 30.0
        elif pet_policy == 'case_by_case':
            return 80.0  # User Feedback: Definitely consider, but not a guaranteed match
        elif pet_policy == 'pet_fee':
            return 95.0  # User Feedback: Minor penalty only
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
        
        # Get detailed reasons for score deductions and matches
        basic_reasons = self._get_basic_requirements_reasons(apartment)
        building_reasons = self._get_building_amenities_reasons(apartment)
        apartment_reasons = self._get_apartment_amenities_reasons(apartment)
        
        # Get positive match reasons
        basic_positives = self._get_basic_requirements_positives(apartment)
        building_positives = self._get_building_amenities_positives(apartment)
        apartment_positives = self._get_apartment_amenities_positives(apartment)
        
        # Combine amenities for simpler display
        combined_amenities_score = (
            (building_score * self.BUILDING_AMENITIES_WEIGHT + 
             apartment_score * self.APARTMENT_AMENITIES_WEIGHT) / 
            (self.BUILDING_AMENITIES_WEIGHT + self.APARTMENT_AMENITIES_WEIGHT)
        ) if (self.BUILDING_AMENITIES_WEIGHT + self.APARTMENT_AMENITIES_WEIGHT) > 0 else 100
        
        combined_amenities_reasons = building_reasons + apartment_reasons
        combined_amenities_positives = building_positives + apartment_positives
            
        return {
            'match_level': match_level,
            'match_color': match_color,
            'basic_score': round(basic_score, 1),
            'building_amenities_score': round(building_score, 1),
            'apartment_amenities_score': round(apartment_score, 1),
            'combined_amenities_score': round(combined_amenities_score, 1),
            'rent_within_budget': apartment.rent_price <= (self.applicant.max_rent_budget or apartment.rent_price),
            'preferred_neighborhood': self._is_preferred_neighborhood(apartment),
            'basic_reasons': basic_reasons,
            'building_reasons': building_reasons,
            'apartment_reasons': apartment_reasons,
            'basic_positives': basic_positives,
            'building_positives': building_positives,
            'apartment_positives': apartment_positives,
            'combined_amenities_reasons': combined_amenities_reasons,
            'combined_amenities_positives': combined_amenities_positives,
        }
    
    def _is_preferred_neighborhood(self, apartment) -> bool:
        """Check if apartment is in a preferred neighborhood"""
        from .models import NeighborhoodPreference
        preferred_neighborhoods = NeighborhoodPreference.objects.filter(
            applicant=self.applicant
        ).values_list('neighborhood__name', flat=True)
        return apartment.building.neighborhood in preferred_neighborhoods
    
    def _get_basic_requirements_reasons(self, apartment) -> List[str]:
        """Get specific reasons for basic requirements score deductions"""
        reasons = []
        
        # Check bedroom mismatch
        apt_bedrooms = float(apartment.bedrooms or 0)
        min_beds = self._convert_bedroom_preference(self.applicant.min_bedrooms)
        max_beds = self._convert_bedroom_preference(self.applicant.max_bedrooms)
        
        if min_beds is not None and apt_bedrooms < min_beds:
            if apt_bedrooms >= min_beds - 0.5:
                reasons.append(f"Studio instead of {int(min_beds)} bedroom preference")
            else:
                reasons.append(f"Has {int(apt_bedrooms)} bedrooms, you wanted {int(min_beds)}+")
        elif max_beds is not None and apt_bedrooms > max_beds:
            reasons.append(f"Has {int(apt_bedrooms)} bedrooms, you wanted max {int(max_beds)}")
        
        # Check bathroom mismatch  
        apt_bathrooms = float(apartment.bathrooms or 1.0)
        min_baths = self._convert_numeric_preference(self.applicant.min_bathrooms)
        max_baths = self._convert_numeric_preference(self.applicant.max_bathrooms)
        
        if min_baths is not None and apt_bathrooms < min_baths:
            reasons.append(f"Has {apt_bathrooms} bath(s), you wanted {min_baths}+")
        elif max_baths is not None and apt_bathrooms > max_baths:
            reasons.append(f"Has {apt_bathrooms} bath(s), you wanted max {max_baths}")
        
        # Check rent overage
        if self.applicant.max_rent_budget and apartment.rent_price > self.applicant.max_rent_budget:
            overage_percent = ((apartment.rent_price - self.applicant.max_rent_budget) / self.applicant.max_rent_budget) * 100
            if overage_percent <= 3:
                reasons.append(f"${int(apartment.rent_price - self.applicant.max_rent_budget)} over budget")
            elif overage_percent <= 6:
                reasons.append(f"${int(apartment.rent_price - self.applicant.max_rent_budget)} over budget")
            elif overage_percent <= 10:
                reasons.append(f"${int(apartment.rent_price - self.applicant.max_rent_budget)} over budget")
        
        # Check neighborhood ranking
        from .models import NeighborhoodPreference
        neighborhood_prefs = NeighborhoodPreference.objects.filter(applicant=self.applicant)
        if neighborhood_prefs.exists():
            apartment_neighborhood = apartment.building.neighborhood
            for pref in neighborhood_prefs:
                if pref.neighborhood.name == apartment_neighborhood:
                    rank = pref.preference_rank
                    if rank > 1:
                        reasons.append(f"#{rank} neighborhood choice")
                    break
        
        # Check pet policy issues
        # CRITICAL FIX #5: Use cached pets to avoid N+1 queries
        # self._pets is already populated in __init__
        has_pets = bool(self._pets)
        
        if has_pets:
            pet_policy = apartment.building.pet_policy
            if pet_policy == 'no_pets':
                reasons.append("Building doesn't allow pets")
            elif pet_policy == 'cats_only':
                # Check if we have any non-cats
                has_non_cats = any(
                    not (hasattr(pet, 'pet_type') and 'cat' in str(pet.pet_type).lower())
                    for pet in self._pets
                )
                if has_non_cats:
                    reasons.append("Building only allows cats")
            elif pet_policy == 'small_pets':
                reasons.append("Pet size may be restricted")
            elif pet_policy == 'case_by_case':
                reasons.append("Pet approval not guaranteed")
            elif pet_policy == 'pet_fee':
                reasons.append("Pet fee required")
        
        return reasons
    
    def _get_building_amenities_reasons(self, apartment) -> List[str]:
        """Get specific reasons for building amenities score deductions"""
        reasons = []
        
        # CRITICAL FIX #4: Use cached building preferences
        building_prefs = self._get_cached_building_preferences()
        if not building_prefs:
            return reasons
        
        building_amenities = set(apartment.building.amenities.values_list('id', flat=True))
        
        for pref in building_prefs:
            amenity_name = pref.amenity.name
            priority_level = pref.priority_level
            amenity_id = pref.amenity.id
            
            if amenity_id not in building_amenities:
                if priority_level == 4:  # Must Have
                    reasons.append(f"Missing required amenity: {amenity_name}")
                elif priority_level == 3:  # Important
                    reasons.append(f"Missing important amenity: {amenity_name}")
        
        return reasons
    
    def _get_apartment_amenities_reasons(self, apartment) -> List[str]:
        """Get specific reasons for apartment amenities score deductions"""
        reasons = []
        
        # CRITICAL FIX #4: Use cached apartment preferences
        apartment_prefs = self._get_cached_apartment_preferences()
        if not apartment_prefs:
            return reasons
        
        apartment_amenities = set(apartment.amenities.values_list('id', flat=True))
        
        for pref in apartment_prefs:
            amenity_name = pref.amenity.name
            priority_level = pref.priority_level
            amenity_id = pref.amenity.id
            
            if amenity_id not in apartment_amenities:
                if priority_level == 4:  # Must Have
                    reasons.append(f"Missing required feature: {amenity_name}")
                elif priority_level == 3:  # Important  
                    reasons.append(f"Missing important feature: {amenity_name}")
        
        return reasons
    
    def _get_basic_requirements_positives(self, apartment) -> List[str]:
        """Get specific reasons why basic requirements matched well"""
        positives = []
        
        # Check bedroom match
        apt_bedrooms = float(apartment.bedrooms or 0)
        min_beds = self._convert_bedroom_preference(self.applicant.min_bedrooms)
        max_beds = self._convert_bedroom_preference(self.applicant.max_bedrooms)
        
        if min_beds is not None and max_beds is not None:
            if min_beds <= apt_bedrooms <= max_beds:
                if apt_bedrooms == 0:
                    positives.append("✓ Studio apartment (as requested)")
                else:
                    positives.append(f"✓ {int(apt_bedrooms)} bedroom{'s' if apt_bedrooms > 1 else ''} (perfect match)")
        elif min_beds is not None and apt_bedrooms >= min_beds:
            positives.append(f"✓ {int(apt_bedrooms)} bedroom{'s' if apt_bedrooms > 1 else ''} meets requirement")
        
        # Check bathroom match
        apt_bathrooms = float(apartment.bathrooms or 1.0)
        min_baths = self._convert_numeric_preference(self.applicant.min_bathrooms)
        max_baths = self._convert_numeric_preference(self.applicant.max_bathrooms)
        
        if min_baths is not None and apt_bathrooms >= min_baths:
            if apt_bathrooms == min_baths:
                positives.append(f"✓ {apt_bathrooms} bathroom{'s' if apt_bathrooms > 1 else ''} (as requested)")
            else:
                positives.append(f"✓ {apt_bathrooms} bathroom{'s' if apt_bathrooms > 1 else ''} (exceeds requirement)")
        
        # Check rent match
        if self.applicant.max_rent_budget:
            if apartment.rent_price <= self.applicant.max_rent_budget:
                savings = self.applicant.max_rent_budget - apartment.rent_price
                if savings > 100:
                    positives.append(f"✓ ${int(savings)} under budget!")
                else:
                    positives.append("✓ Within budget")
        
        # Check neighborhood match
        # CRITICAL FIX #4: Use cached neighborhood data
        if not hasattr(self, '_neighborhood_rank_cache'):
            from .models import NeighborhoodPreference
            self._neighborhood_rank_cache = {}
            neighborhood_prefs = NeighborhoodPreference.objects.filter(
                applicant=self.applicant
            ).select_related('neighborhood')
            for pref in neighborhood_prefs:
                self._neighborhood_rank_cache[pref.neighborhood.name] = pref.preference_rank
        
        apartment_neighborhood = apartment.building.neighborhood
        if apartment_neighborhood in self._neighborhood_rank_cache:
            rank = self._neighborhood_rank_cache[apartment_neighborhood]
            if rank == 1:
                positives.append(f"✓ {apartment_neighborhood} (your #1 choice!)")
            elif rank == 2:
                positives.append(f"✓ {apartment_neighborhood} (your #2 choice)")
            elif rank == 3:
                positives.append(f"✓ {apartment_neighborhood} (your #3 choice)")
        else:
            positives.append(f"✓ Located in {apartment.building.neighborhood}")
        
        # Check pet policy match
        # CRITICAL FIX #4: Use cached pet data
        cached_pets = self._get_cached_pets()
        has_pets = len(cached_pets) > 0
        if has_pets:
            pet_policy = apartment.building.pet_policy
            if pet_policy == 'all_pets':
                positives.append("✓ All pets welcome!")
            elif pet_policy == 'pet_fee':
                positives.append("✓ Pets allowed (with fee)")
        elif not has_pets and apartment.building.pet_policy == 'no_pets':
            positives.append("✓ No pet restrictions apply to you")
            
        # Check move-in date match
        if self.applicant.desired_move_in_date:
            # Since we strict filter, all shown apartments are available by date.
            # We can try to be specific if we have the date.
            availability = apartment.get_current_availability()
            if availability and availability.available_date:
                if availability.available_date <= self.applicant.desired_move_in_date:
                    positives.append(f"✓ Available by {self.applicant.desired_move_in_date.strftime('%b %d')}")
            else:
                # No specific date usually means available now
                positives.append("✓ Available for immediate move-in")
        
        return positives
    
    def _get_building_amenities_positives(self, apartment) -> List[str]:
        """Get specific building amenities that match preferences"""
        positives = []
        
        # CRITICAL FIX #4: Use cached building preferences
        building_prefs = self._get_cached_building_preferences()
        if not building_prefs:
            return positives
        
        building_amenities = set(apartment.building.amenities.values_list('id', flat=True))
        building_amenity_names = dict(apartment.building.amenities.values_list('id', 'name'))
        
        # Group by priority for better presentation
        must_haves = []
        important = []
        nice_to_haves = []
        
        for pref in building_prefs:
            amenity_name = pref.amenity.name
            priority_level = pref.priority_level
            amenity_id = pref.amenity.id
            
            if amenity_id in building_amenities:
                if priority_level == 4:  # Must Have
                    must_haves.append(amenity_name)
                elif priority_level == 3:  # Important
                    important.append(amenity_name)
                elif priority_level == 2:  # Nice to Have
                    nice_to_haves.append(amenity_name)
        
        if must_haves:
            positives.append(f"✓ Has required: {', '.join(must_haves[:3])}")
        if important:
            positives.append(f"✓ Has important: {', '.join(important[:3])}")
        if nice_to_haves:
            positives.append(f"✓ Bonus amenities: {', '.join(nice_to_haves[:3])}")
        
        return positives
    
    def _get_apartment_amenities_positives(self, apartment) -> List[str]:
        """Get specific apartment features that match preferences"""
        positives = []
        
        # CRITICAL FIX #4: Use cached apartment preferences
        apartment_prefs = self._get_cached_apartment_preferences()
        if not apartment_prefs:
            return positives
        
        apartment_amenities = set(apartment.amenities.values_list('id', flat=True))
        
        # Group by priority for better presentation
        must_haves = []
        important = []
        nice_to_haves = []
        
        for pref in apartment_prefs:
            amenity_name = pref.amenity.name
            priority_level = pref.priority_level
            amenity_id = pref.amenity.id
            
            if amenity_id in apartment_amenities:
                if priority_level == 4:  # Must Have
                    must_haves.append(amenity_name)
                elif priority_level == 3:  # Important
                    important.append(amenity_name)
                elif priority_level == 2:  # Nice to Have
                    nice_to_haves.append(amenity_name)
        
        if must_haves:
            positives.append(f"✓ Has required: {', '.join(must_haves[:3])}")
        if important:
            positives.append(f"✓ Has important: {', '.join(important[:3])}")
        if nice_to_haves:
            positives.append(f"✓ Bonus features: {', '.join(nice_to_haves[:3])}")
        
        return positives


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