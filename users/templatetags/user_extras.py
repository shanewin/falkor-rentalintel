from django import template

register = template.Library()

@register.simple_tag
def get_user_profile_info(user):
    """
    Get user profile information based on their role.
    Returns a dictionary with display_name, profile_photo, and email.
    """
    if not user or not user.is_authenticated:
        return {
            'display_name': '',
            'profile_photo': None,
            'email': '',
        }
    
    profile = None
    display_name = None
    profile_photo = None
    
    # Check user role and get appropriate profile
    try:
        if user.is_superuser:
            profile = getattr(user, 'admin_profile', None)
        elif user.is_staff:
            profile = getattr(user, 'staff_profile', None)
        elif user.is_broker:
            profile = getattr(user, 'broker_profile', None)
        elif user.is_applicant:
            profile = getattr(user, 'applicant_profile', None)
        elif user.is_owner:
            profile = getattr(user, 'owner_profile', None)
    except AttributeError:
        profile = None
    
    # Get display name from profile
    position = None
    job_title = None
    
    if profile:
        first_name = getattr(profile, 'first_name', '').strip()
        last_name = getattr(profile, 'last_name', '').strip()
        
        if first_name and last_name:
            display_name = f"{first_name} {last_name}"
        elif first_name:
            display_name = first_name
        elif last_name:
            display_name = last_name
        
        # Get profile photo
        profile_photo = getattr(profile, 'profile_photo', None)
        
        # Get position or job_title
        position = getattr(profile, 'position', None)
        job_title = getattr(profile, 'job_title', None)
    
    # Fallback to email if no name available
    if not display_name:
        display_name = user.email
    
    return {
        'display_name': display_name,
        'profile_photo': profile_photo,
        'email': user.email,
        'position': position,
        'job_title': job_title,
    }

@register.simple_tag
def get_user_avatar_url(user, size=40):
    """
    Get user avatar URL with fallback to default avatar.
    """
    profile_info = get_user_profile_info(user)
    
    if profile_info['profile_photo']:
        # If using Cloudinary, we can add transformations
        try:
            # Check if it's a Cloudinary field
            photo = profile_info['profile_photo']
            if hasattr(photo, 'build_url'):
                return photo.build_url(
                    width=size, 
                    height=size, 
                    crop="fill", 
                    gravity="face",
                    radius="max",
                    quality="auto:best",
                    dpr="2.0",
                    fetch_format="auto"
                )
            else:
                return str(photo)
        except:
            pass
    
    # Fallback to default avatar or initial-based avatar
    return None

@register.simple_tag
def get_user_initials(user):
    """
    Get user initials for avatar fallback.
    """
    profile_info = get_user_profile_info(user)
    display_name = profile_info['display_name']
    
    if display_name and display_name != user.email:
        # Extract initials from name
        parts = display_name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[-1][0]}".upper()
        elif len(parts) == 1:
            return parts[0][:2].upper()
    
    # Fallback to email initials
    if user.email:
        return user.email[0].upper()
    
    return "U"

@register.simple_tag
def get_user_profile_url(user):
    """
    Get the appropriate profile URL based on user role.
    """
    if not user or not user.is_authenticated:
        return None
    
    if user.is_superuser:
        return '/users/profile/admin/'
    elif user.is_staff:
        return '/users/profile/staff/'
    elif user.is_broker:
        return '/users/profile/broker/'
    elif user.is_owner:
        return '/users/profile/owner/'
    elif user.is_applicant:
        return '/applicants/my-profile/'
    
    return None

@register.simple_tag
def get_user_profile_completion(user):
    """
    Get user profile completion percentage based on their role.
    """
    if not user or not user.is_authenticated:
        return 0
    
    try:
        from applications.services import ProfileProgressService
        
        if user.is_superuser:
            # NO completion tracking for admins - return 0 to hide completion display
            return 0
        elif user.is_staff:
            profile = getattr(user, 'staff_profile', None)
            if profile:
                completion, _ = ProfileProgressService.calculate_staff_profile_completion(profile)
                return completion
        elif user.is_broker:
            profile = getattr(user, 'broker_profile', None)
            if profile:
                completion, _ = ProfileProgressService.calculate_broker_profile_completion(profile)
                return completion
        elif user.is_owner:
            profile = getattr(user, 'owner_profile', None)
            if profile:
                completion, _ = ProfileProgressService.calculate_owner_profile_completion(profile)
                return completion
        elif user.is_applicant:
            profile = getattr(user, 'applicant_profile', None)
            if profile:
                completion, _ = ProfileProgressService.calculate_applicant_profile_completion(profile)
                return completion
    except Exception:
        # If there's any error (missing service, profile, etc.), return 0
        pass
    
    return 0