from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
import logging

logger = logging.getLogger(__name__)


def authenticated_required(view_func):
    """
    Decorator that allows access to authenticated users (brokers, applicants, staff, superusers).
    Used for read-only building views where all authenticated users can view information.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to access this page.")
            return redirect('login')
            
        # Log access for security monitoring
        logger.info(
            f"Buildings read access by user {request.user.email} "
            f"(superuser: {request.user.is_superuser}, staff: {request.user.is_staff}, "
            f"broker: {getattr(request.user, 'is_broker', False)}, "
            f"applicant: {getattr(request.user, 'is_applicant', False)})"
        )
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_only(view_func):
    """
    Decorator that restricts access to admin users only (superusers and staff).
    Used for create/edit operations that only admins should perform.
    
    Security Note: This decorator provides multi-layer protection:
    1. Authentication check
    2. Admin privilege verification 
    3. Explicit blocking of non-admin roles for write operations
    4. Logging of unauthorized access attempts
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # First check if user is authenticated
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to access this page.")
            return redirect('login')
        
        # Check if user has admin privileges (superuser or staff)
        if not (request.user.is_superuser or request.user.is_staff):
            # Log the unauthorized access attempt for security monitoring
            logger.warning(
                f"Unauthorized buildings edit attempt by user {request.user.email} "
                f"(broker: {getattr(request.user, 'is_broker', False)}, "
                f"applicant: {getattr(request.user, 'is_applicant', False)}, "
                f"owner: {getattr(request.user, 'is_owner', False)})"
            )
            
            messages.error(request, 
                "🚫 Access denied. Building creation and editing requires administrator privileges. "
                "You can view building information but cannot make changes."
            )
            return redirect('buildings_list')  # Redirect to read-only list instead of home
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def staff_required(user):
    """
    Function for use with @user_passes_test decorator.
    Returns True if user is staff or superuser.
    """
    return user.is_authenticated and (user.is_superuser or user.is_staff)