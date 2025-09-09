from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from django.http import HttpResponseForbidden
import secrets
import string
from .models import User
from .forms import LoginForm, BrokerRegistrationForm, ApplicantRegistrationForm, StaffRegistrationForm, OwnerRegistrationForm


def require_superuser_or_staff(view_func):
    """Decorator to require superuser or staff access"""
    def check_superuser_or_staff(user):
        return user.is_authenticated and (user.is_superuser or user.is_staff)
    
    return user_passes_test(check_superuser_or_staff)(view_func)


def user_login(request):
    """Custom login view with role-based redirection"""
    if request.user.is_authenticated:
        return redirect_by_role(request.user)
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(request, f"Welcome back, {user.email}!")
                
                # Redirect to 'next' parameter if it exists, otherwise role-based redirect
                next_url = request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect_by_role(user)
            else:
                messages.error(request, "Invalid email or password.")
    else:
        form = LoginForm()
    
    return render(request, 'users/login.html', {'form': form})


def user_logout(request):
    """Logout view"""
    logout(request)
    messages.success(request, "You have been successfully logged out.")
    return redirect('login')


def redirect_by_role(user):
    """Redirect user based on their role"""
    if user.is_superuser:
        return redirect('admin_dashboard')
    elif user.is_staff:
        return redirect('staff_dashboard')
    elif user.is_broker:
        return redirect('broker_dashboard')
    elif user.is_applicant:
        return redirect('applicant_dashboard')
    elif user.is_owner:
        return redirect('owner_dashboard')
    else:
        return redirect('home')


@login_required
def register_broker(request):
    """Admin-only registration view for brokers"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied. Only administrators can create broker accounts.")
        return redirect_by_role(request.user)
    
    if request.method == 'POST':
        form = BrokerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_broker = True
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            # Send invitation email
            send_account_invitation_email(user, 'broker', form.cleaned_data['password'])
            
            messages.success(request, f"Broker account created for {user.email} and invitation email sent.")
            return redirect('admin_user_management')
    else:
        form = BrokerRegistrationForm()
    
    return render(request, 'users/admin/create_broker.html', {'form': form})


def register_applicant(request):
    """Registration view for applicants - creates both User and Applicant profile"""
    if request.user.is_authenticated:
        return redirect_by_role(request.user)
    
    if request.method == 'POST':
        form = ApplicantRegistrationForm(request.POST)
        if form.is_valid():
            # Create User account
            user = form.save(commit=False)
            user.is_applicant = True
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            # Create or update Applicant profile
            from applicants.models import Applicant
            from django.utils import timezone
            
            # Check if an applicant with this email already exists (from previous application)
            applicant, created = Applicant.objects.get_or_create(
                email=user.email,
                defaults={
                    'first_name': form.cleaned_data.get('first_name', ''),
                    'last_name': form.cleaned_data.get('last_name', ''),
                    'phone_number': form.cleaned_data.get('phone_number', ''),
                    'date_of_birth': timezone.now().date(),  # Temporary, user will update
                    'street_address_1': '',  # User will fill progressively
                    'city': '',
                    'state': 'NY',
                    'zip_code': '',
                }
            )
            
            # Link the applicant profile to the user account
            applicant.user = user
            if not created:
                # Update existing applicant with new info if provided
                applicant.first_name = form.cleaned_data.get('first_name', applicant.first_name)
                applicant.last_name = form.cleaned_data.get('last_name', applicant.last_name)
                if form.cleaned_data.get('phone_number'):
                    applicant.phone_number = form.cleaned_data['phone_number']
            applicant.save()
            
            # Auto-login after registration
            user = authenticate(username=user.email, password=form.cleaned_data['password'])
            login(request, user)
            
            messages.success(request, "Welcome! Your account has been created. You can now complete your profile.")
            return redirect('applicant_dashboard')
    else:
        form = ApplicantRegistrationForm()
    
    return render(request, 'users/register_applicant.html', {'form': form})


@login_required
def register_staff(request):
    """Admin-only registration view for staff"""
    if not request.user.is_superuser:
        messages.error(request, "Access denied. Only superusers can create staff accounts.")
        return redirect_by_role(request.user)
    
    if request.method == 'POST':
        form = StaffRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = True
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            # Send invitation email
            send_account_invitation_email(user, 'staff', form.cleaned_data['password'])
            
            messages.success(request, f"Staff account created for {user.email} and invitation email sent.")
            return redirect('admin_user_management')
    else:
        form = StaffRegistrationForm()
    
    return render(request, 'users/admin/create_staff.html', {'form': form})


@login_required
def register_owner(request):
    """Admin-only registration view for property owners"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied. Only administrators can create owner accounts.")
        return redirect_by_role(request.user)
    
    if request.method == 'POST':
        form = OwnerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_owner = True
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            # Send invitation email
            send_account_invitation_email(user, 'owner', form.cleaned_data['password'])
            
            messages.success(request, f"Owner account created for {user.email} and invitation email sent.")
            return redirect('admin_user_management')
    else:
        form = OwnerRegistrationForm()
    
    return render(request, 'users/admin/create_owner.html', {'form': form})


@login_required
def admin_dashboard(request):
    """Dashboard for admin/staff users"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied. Admin privileges required.")
        return redirect_by_role(request.user)
    
    # Get admin profile if it exists
    from .profiles_models import AdminProfile
    try:
        admin_profile = AdminProfile.objects.get(user=request.user)
    except AdminProfile.DoesNotExist:
        admin_profile = None
    
    # Import models for statistics
    from buildings.models import Building
    from applications.models import Application, ApplicationActivity
    from apartments.models import Apartment
    from applicants.models import Applicant
    from django.utils import timezone
    from datetime import timedelta
    
    # Rental Management Statistics
    building_count = Building.objects.count()
    available_apartments = Apartment.objects.filter(status='available').count()
    unplaced_applicants = Applicant.objects.filter(placement_status='unplaced').count()
    pending_reviews = Application.objects.filter(status__in=['PENDING', 'COMPLETED']).count()
    
    # User type distribution
    broker_count = User.objects.filter(is_broker=True).count()
    applicant_count = User.objects.filter(is_applicant=True).count()
    owner_count = User.objects.filter(is_owner=True).count()
    staff_count = User.objects.filter(is_staff=True, is_superuser=False).count()
    superuser_count = User.objects.filter(is_superuser=True).count()
    
    # Recent activity from application logs
    recent_activities = ApplicationActivity.objects.select_related('application', 'application__applicant').order_by('-timestamp')[:10]
    
    # Recent user registrations (last 7 days)
    seven_days_ago = timezone.now() - timedelta(days=7)
    recent_users = User.objects.filter(created_at__gte=seven_days_ago).order_by('-created_at')[:5]
    
    # Recent applications (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_applications = Application.objects.filter(created_at__gte=thirty_days_ago).select_related('applicant', 'apartment__building').order_by('-created_at')[:5]
    
    context = {
        'user': request.user,
        'admin_profile': admin_profile,
        'is_admin': True,
        # Rental Management Statistics
        'building_count': building_count,
        'available_apartments': available_apartments,
        'unplaced_applicants': unplaced_applicants,
        'pending_reviews': pending_reviews,
        # User distribution
        'broker_count': broker_count,
        'applicant_count': applicant_count,
        'owner_count': owner_count,
        'staff_count': staff_count,
        'superuser_count': superuser_count,
        # Activity data
        'recent_activities': recent_activities,
        'recent_users': recent_users,
        'recent_applications': recent_applications,
        # Additional apartment and applicant metrics
        'total_apartments': Apartment.objects.count(),
        'rented_apartments': Apartment.objects.filter(status='rented').count(),
        'total_applicants': Applicant.objects.count(),
        'placed_applicants': Applicant.objects.filter(placement_status='placed').count(),
    }
    return render(request, 'users/dashboards/admin_dashboard.html', context)


@login_required
def broker_dashboard(request):
    """Dashboard for brokers"""
    if not request.user.is_broker and not request.user.is_superuser:
        messages.error(request, "Access denied. Broker privileges required.")
        return redirect_by_role(request.user)
    
    # Get broker's recent applications
    from applications.models import Application
    recent_applications = Application.objects.filter(broker=request.user).order_by('-created_at')[:5]
    
    context = {
        'user': request.user,
        'recent_applications': recent_applications,
    }
    return render(request, 'users/dashboards/broker_dashboard.html', context)


@login_required
def applicant_dashboard(request):
    """Dashboard for applicants with profile progress"""
    if not request.user.is_applicant and not request.user.is_superuser:
        messages.error(request, "Access denied. Applicant privileges required.")
        return redirect_by_role(request.user)
    
    # Get applicant's applications
    from applicants.models import Applicant
    from applications.models import Application
    from applications.services import ProfileProgressService
    from applicants.apartment_matching import get_apartment_matches_for_applicant
    
    try:
        # Try to get applicant by user first, then by email
        try:
            applicant = request.user.applicant_profile
        except Applicant.DoesNotExist:
            applicant = Applicant.objects.get(email=request.user.email)
            # Link the applicant to the user if not already linked
            if not applicant.user:
                applicant.user = request.user
                applicant.save()
        
        applications = Application.objects.filter(applicant=applicant).order_by('-created_at')
        
        # Get profile completion status
        completion_percentage, missing_fields = ProfileProgressService.calculate_profile_completion(applicant)
        next_steps = ProfileProgressService.get_next_profile_steps(applicant)
        
        # Get apartment matches if profile has basic preferences
        apartment_matches = []
        if completion_percentage >= 25 and applicant.max_rent_budget:  # Show matches if basic preferences set
            try:
                apartment_matches = get_apartment_matches_for_applicant(applicant, limit=6)
            except Exception as e:
                # Log error but don't break dashboard
                import logging
                logging.error(f"Error getting apartment matches for applicant {applicant.id}: {str(e)}")
        
    except Applicant.DoesNotExist:
        applicant = None
        applications = []
        completion_percentage = 0
        missing_fields = {}
        next_steps = ["Create your applicant profile to get started"]
        apartment_matches = []
    
    context = {
        'user': request.user,
        'applicant': applicant,
        'applications': applications,
        'completion_percentage': completion_percentage,
        'profile_incomplete': completion_percentage < 100,
        'next_steps': next_steps,
        'apartment_matches': apartment_matches,
        'has_matches': len(apartment_matches) > 0,
    }
    return render(request, 'users/dashboards/applicant_dashboard.html', context)


@login_required
def owner_dashboard(request):
    """Dashboard for property owners"""
    if not request.user.is_owner and not request.user.is_superuser:
        messages.error(request, "Access denied. Owner privileges required.")
        return redirect_by_role(request.user)
    
    context = {
        'user': request.user,
    }
    return render(request, 'users/dashboards/owner_dashboard.html', context)


@login_required
def staff_dashboard(request):
    """Dashboard for staff members (distinct from superusers)"""
    if not request.user.is_staff or request.user.is_superuser:
        messages.error(request, "Access denied. Staff privileges required.")
        return redirect_by_role(request.user)
    
    context = {
        'user': request.user,
    }
    return render(request, 'users/dashboards/staff_dashboard.html', context)


def generate_temporary_password(length=12):
    """Generate a secure temporary password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    password = ''.join(secrets.choice(alphabet) for i in range(length))
    return password


def send_account_invitation_email(user, role, temporary_password):
    """Send invitation email to new user with temporary password"""
    try:
        subject = f"Welcome to Doorway - Your {role.title()} Account"
        
        # Create the email context
        context = {
            'user': user,
            'role': role.title(),
            'temporary_password': temporary_password,
            'login_url': f"{settings.SITE_URL}/users/login/" if hasattr(settings, 'SITE_URL') else "http://localhost:8000/users/login/",
        }
        
        # Render email template
        html_message = render_to_string('users/emails/account_invitation.html', context)
        plain_message = strip_tags(html_message)
        
        # Send email using the configured backend (SendGrid/Mailgun/Console)
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Failed to send invitation email: {e}")
        return False


@login_required
def admin_user_management(request):
    """Admin interface for managing user accounts"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied. Administrator privileges required.")
        return redirect_by_role(request.user)
    
    # Get user statistics
    total_users = User.objects.count()
    brokers = User.objects.filter(is_broker=True).order_by('-created_at')[:10]
    staff = User.objects.filter(is_staff=True).order_by('-created_at')[:10]
    owners = User.objects.filter(is_owner=True).order_by('-created_at')[:10]
    applicants = User.objects.filter(is_applicant=True).order_by('-created_at')[:10]
    
    context = {
        'total_users': total_users,
        'broker_count': User.objects.filter(is_broker=True).count(),
        'staff_count': User.objects.filter(is_staff=True).count(),
        'owner_count': User.objects.filter(is_owner=True).count(),
        'applicant_count': User.objects.filter(is_applicant=True).count(),
        'recent_brokers': brokers,
        'recent_staff': staff,
        'recent_owners': owners,
        'recent_applicants': applicants,
    }
    
    return render(request, 'users/admin/user_management.html', context)


@login_required
def admin_create_account(request, account_type):
    """Generic admin view for creating different account types"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied. Administrator privileges required.")
        return redirect_by_role(request.user)
    
    # Check if staff can create this account type
    if request.user.is_staff and not request.user.is_superuser:
        if account_type in ['staff']:  # Only superuser can create staff accounts
            messages.error(request, "Access denied. Only superusers can create staff accounts.")
            return redirect('admin_user_management')
    
    if request.method == 'POST':
        email = request.POST.get('email')
        
        if User.objects.filter(email=email).exists():
            messages.error(request, "A user with this email already exists.")
        else:
            # Generate temporary password
            temp_password = generate_temporary_password()
            
            # Create user
            user = User.objects.create_user(
                email=email,
                password=temp_password
            )
            
            # Set role
            if account_type == 'broker':
                user.is_broker = True
            elif account_type == 'staff':
                user.is_staff = True
            elif account_type == 'owner':
                user.is_owner = True
            
            user.save()
            
            # Send invitation email
            if send_account_invitation_email(user, account_type, temp_password):
                messages.success(request, f"{account_type.title()} account created for {email} and invitation email sent.")
            else:
                messages.warning(request, f"{account_type.title()} account created for {email}, but email sending failed.")
            
            return redirect('admin_user_management')
    
    return render(request, 'users/admin/create_account.html', {
        'account_type': account_type,
        'account_type_title': account_type.title()
    })


@require_superuser_or_staff  
def broker_leaderboard(request):
    """
    Display broker performance leaderboard with comprehensive metrics and rankings
    """
    from .broker_leaderboard import BrokerLeaderboardService
    
    service = BrokerLeaderboardService()
    
    # Get leaderboard data
    leaderboard = service.get_broker_leaderboard(limit=50)
    summary_stats = service.get_broker_summary_stats()
    
    # Get time period for display
    from django.utils import timezone
    current_date = timezone.now()
    
    context = {
        'leaderboard': leaderboard,
        'summary_stats': summary_stats,
        'current_date': current_date,
        'total_brokers': len(leaderboard),
        'has_data': len(leaderboard) > 0,
    }
    
    return render(request, 'users/admin/broker_leaderboard.html', context)
