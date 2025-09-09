import logging
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.contrib import messages

logger = logging.getLogger(__name__)


class BuildingsSecurityMiddleware(MiddlewareMixin):
    """
    Middleware to provide additional security for buildings app.
    Logs all access attempts and provides additional protection layer.
    """
    
    def process_request(self, request):
        # Check if this is a request to the buildings app
        if request.path.startswith('/buildings/'):
            # Log all buildings access attempts
            user_info = "anonymous"
            if request.user.is_authenticated:
                user_info = f"{request.user.email} (superuser: {request.user.is_superuser}, staff: {request.user.is_staff})"
            
            logger.info(f"Buildings access attempt: {request.path} by {user_info} from IP {self.get_client_ip(request)}")
            
            # Check if this is a create/edit operation (admin-only)
            admin_only_paths = ['/buildings/create/', '/buildings/']
            is_admin_only = any(request.path.startswith(path) for path in admin_only_paths)
            
            # For admin-only operations, check if it's a POST request or create/detail path with edit intent
            if (request.path.startswith('/buildings/create/') or 
                (request.method == 'POST' and request.path.startswith('/buildings/')) or
                ('detail' in request.path and request.method == 'POST')):
                
                if request.user.is_authenticated and not (request.user.is_superuser or request.user.is_staff):
                    logger.warning(f"Blocked non-admin user {request.user.email} from edit operation at {request.path}")
                    messages.error(request, 
                        "🚫 Access denied. Building creation and editing requires administrator privileges."
                    )
                    return redirect('buildings_list')
        
        return None
    
    def get_client_ip(self, request):
        """Get the client's IP address."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip