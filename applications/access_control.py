"""
Centralized access control for application views.

All application endpoints should use validate_application_access() 
to determine who is accessing the application and whether they're authorized.

Role hierarchy:
- Superuser: full access to all applications
- Broker: access to applications they're assigned to (or staff+broker for all)
- Owner: (FUTURE) access to applications for their buildings
- Applicant: access to their own application only (via token or session)
"""

from django.shortcuts import redirect
from django.contrib import messages


def validate_application_access(request, application):
    """
    Validate that the requesting user has access to this application.
    
    Returns:
        tuple: (access_type, error_response)
            - access_type: 'applicant', 'broker', or None
            - error_response: HttpResponse if access denied, else None
    
    Usage:
        access_type, error = validate_application_access(request, application)
        if error:
            return error
        is_applicant_access = (access_type == 'applicant')
    """
    token = request.GET.get('token')
    
    # 1. Token-based applicant access (no login required)
    if token and token == str(application.unique_link):
        return 'applicant', None
    
    # 2. Session-based applicant access (logged-in owner of this application)
    if (request.user.is_authenticated and 
        application.applicant and 
        application.applicant.user == request.user):
        return 'applicant', None
    
    # 3. Superuser — full access (treated as broker-level for UI purposes)
    if request.user.is_authenticated and request.user.is_superuser:
        return 'broker', None
    
    # 4. Assigned broker — access to their own applications
    if (request.user.is_authenticated and 
        request.user.is_broker and
        request.user == application.broker):
        return 'broker', None
    
    # 5. Staff + broker — access to all applications (staff brokers)
    if (request.user.is_authenticated and 
        request.user.is_staff and 
        request.user.is_broker):
        return 'broker', None
    
    # 6. Owner access (FUTURE — requires Building.owners M2M field)
    # When Building.owners is added, uncomment:
    # if (request.user.is_authenticated and
    #     request.user.is_owner and
    #     application.apartment and
    #     application.apartment.building.owners.filter(id=request.user.id).exists()):
    #     return 'owner', None
    
    # === Access Denied ===
    if not request.user.is_authenticated:
        return None, redirect('login')
    
    messages.error(request, "You are not authorized to access this application.")
    return None, redirect('applications_list')
