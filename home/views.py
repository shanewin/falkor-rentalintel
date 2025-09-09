from django.shortcuts import render, redirect
from users.views import redirect_by_role


def home(request):
    """
    Homepage that redirects authenticated users to their role-based dashboard
    or shows login/registration options for anonymous users
    """
    # If user is authenticated, redirect them to their dashboard
    if request.user.is_authenticated:
        return redirect_by_role(request.user)
    
    # For anonymous users, show login/registration page
    return render(request, 'home/home.html', {
        'logo_url': '/static/images/falkor-horizontal-transparent-blacktext.png',
        'show_auth_options': True
    })
