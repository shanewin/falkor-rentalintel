from allauth.account.signals import user_signed_up
from django.dispatch import receiver
from .models import User
from applicants.models import Applicant

@receiver(user_signed_up)
def create_applicant_profile(request, user, **kwargs):
    """
    Signal handler to create an Applicant profile when a user signs up via Google (or any other social provider).
    """
    # Check if the user already has a profile (shouldn't happen on signup, but good for safety)
    if not hasattr(user, 'applicant_profile') and not hasattr(user, 'broker_profile') and not hasattr(user, 'owner_profile') and not hasattr(user, 'staff_profile'):
        # Default to Applicant profile for social signups
        Applicant.objects.create(user=user)
        user.is_applicant = True
        user.save()
