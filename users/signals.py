from allauth.account.signals import user_signed_up
from django.dispatch import receiver
from .models import User
from applicants.models import Applicant

@receiver(user_signed_up)
def create_applicant_profile(request, user, **kwargs):
    """
    Signal handler to create an Applicant profile when a user signs up via Google (or any other social provider).
    Ensures identity information (Name, Email) is saved to the User model.
    """
    # Extract social login data if available
    sociallogin = kwargs.get('sociallogin')
    if sociallogin and sociallogin.account.provider == 'google':
        data = sociallogin.account.extra_data
        
        # Update User identity fields if not already set
        if not user.first_name and data.get('given_name'):
            user.first_name = data.get('given_name')
        if not user.last_name and data.get('family_name'):
            user.last_name = data.get('family_name')
        
        # Email is usually handled by allauth, but ensuring it doesn't hurt
        if not user.email and data.get('email'):
            user.email = data.get('email')
            
        user.save()

    # Check if the user already has a profile (shouldn't happen on signup, but good for safety)
    if not hasattr(user, 'applicant_profile') and not hasattr(user, 'broker_profile') and not hasattr(user, 'owner_profile') and not hasattr(user, 'staff_profile'):
        # Default to Applicant profile for social signups
        Applicant.objects.create(user=user)
        user.is_applicant = True
        user.save()
