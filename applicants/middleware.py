"""
Activity Tracking Middleware
============================

Middleware to capture the current request user for activity tracking.
"""

from threading import local

_thread_locals = local()


def get_current_user():
    """Get the current user from thread local storage"""
    return getattr(_thread_locals, 'user', None)


def get_current_request():
    """Get the current request from thread local storage"""
    return getattr(_thread_locals, 'request', None)


class ActivityTrackingMiddleware:
    """
    Middleware to store the current user and request in thread local storage
    for access by signal handlers and activity tracking.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Store request and user in thread local storage
        _thread_locals.user = getattr(request, 'user', None)
        _thread_locals.request = request
        
        try:
            response = self.get_response(request)
        finally:
            # Clean up thread locals after request
            if hasattr(_thread_locals, 'user'):
                del _thread_locals.user
            if hasattr(_thread_locals, 'request'):
                del _thread_locals.request
        
        return response