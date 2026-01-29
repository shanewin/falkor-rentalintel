from django import template
from applicants.models import ApplicantBuildingAmenityPreference, ApplicantApartmentAmenityPreference
from buildings.models import Amenity as BuildingAmenity
from apartments.models import ApartmentAmenity

register = template.Library()

@register.filter
def get_amenity_priority(applicant, amenity):
    """
    Returns the priority level (2, 3, 4) for a given amenity and applicant.
    Returns 0 if no preference is found.
    """
    if not applicant or not amenity:
        return 0
    
    try:
        if isinstance(amenity, BuildingAmenity):
            pref = ApplicantBuildingAmenityPreference.objects.filter(
                applicant=applicant,
                amenity=amenity
            ).first()
            return pref.priority_level if pref else 0
        elif isinstance(amenity, ApartmentAmenity):
            pref = ApplicantApartmentAmenityPreference.objects.filter(
                applicant=applicant,
                amenity=amenity
            ).first()
            return pref.priority_level if pref else 0
    except Exception:
        return 0
    
    return 0

@register.filter
def priority_label(level):
    """Converts priority level to human-readable label"""
    mapping = {
        2: 'Nice to Have',
        3: 'Important',
        4: 'Must Have'
    }
    return mapping.get(level, '')

@register.filter
def priority_class(level):
    """Returns CSS class for priority level"""
    mapping = {
        2: 'bg-info',
        3: 'bg-primary',
        4: 'bg-warning text-dark'
    }
    return mapping.get(level, '')
