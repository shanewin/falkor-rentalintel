from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login
from django.views.decorators.http import require_http_methods
from django.db import transaction
from .models import Application
from .services import AccountCreationService, ApplicationDataService
from users.forms import PostApplicationAccountForm
from users.models import User
from applicants.models import Applicant


@require_http_methods(["GET", "POST"])
def create_account_after_application(request, uuid):
    """
    Allow applicants to create an account after completing an application
    """
    application = get_object_or_404(Application, unique_link=uuid)
    
    # Check if application was submitted
    if not application.submitted_by_applicant:
        messages.warning(request, "Please complete your application first.")
        return redirect('applicant_complete', uuid=uuid)
    
    # Check if user already has an account
    if application.applicant and application.applicant.user:
        messages.info(request, "You already have an account. Please log in.")
        return redirect('login')
    
    if request.method == 'POST':
        form = PostApplicationAccountForm(request.POST)
        if form.is_valid() and form.cleaned_data.get('create_account'):
            password = form.cleaned_data['password']
            email = application.applicant.email if application.applicant else None
            
            if not email:
                messages.error(request, "Unable to create account - no email found.")
                return redirect('home')
            
            with transaction.atomic():
                # Create user account
                user, error = AccountCreationService.create_account_from_application(
                    email=email,
                    password=password,
                    application=application
                )
                
                if error:
                    messages.error(request, error)
                    return render(request, 'applications/create_account.html', {
                        'form': form,
                        'application': application
                    })
                
                # Link anonymous applications
                linked_apps = AccountCreationService.link_anonymous_applications(user)
                
                # Auto-login
                login(request, user)
                
                messages.success(request, 
                    f"Account created successfully! "
                    f"{'We linked ' + str(len(linked_apps)) + ' application(s) to your account.' if linked_apps else ''}"
                )
                
                return redirect('applicant_dashboard')
        elif not form.cleaned_data.get('create_account'):
            # User chose not to create account
            messages.info(request, "You can create an account anytime using the link in your email.")
            return redirect('home')
    else:
        form = PostApplicationAccountForm()
    
    return render(request, 'applications/create_account.html', {
        'form': form,
        'application': application
    })


def application_completion_success(request, uuid):
    """
    Success page after application completion with option to create account
    """
    application = get_object_or_404(Application, unique_link=uuid)
    
    # Check if user already has an account
    has_account = False
    if application.applicant and application.applicant.user:
        has_account = True
    
    return render(request, 'applications/completion_success.html', {
        'application': application,
        'has_account': has_account,
        'create_account_url': f"/applications/create-account/{uuid}/"
    })