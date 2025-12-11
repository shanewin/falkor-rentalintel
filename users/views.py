from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.conf import settings
from django.http import HttpResponseForbidden, Http404
import logging
from .models import User
from .forms import LoginForm, BrokerRegistrationForm, ApplicantRegistrationForm, StaffRegistrationForm, OwnerRegistrationForm
from .token_utils import (
    generate_invitation_link,
    generate_activation_link,
    verify_token,
    invitation_token,
    account_activation_token
)

logger = logging.getLogger(__name__)


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
                
                # FIX: Validate 'next' parameter to prevent open redirect attacks
                next_url = request.GET.get('next')
                if next_url and url_has_allowed_host_and_scheme(
                    url=next_url,
                    allowed_hosts={request.get_host()},
                    require_https=request.is_secure()
                ):
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
        return redirect('apartments_list')


@login_required
def register_broker(request):
    """Admin-only registration view for brokers"""
    if not (request.user.is_superuser or request.user.is_staff):
        messages.error(request, "Access denied. Only administrators can create broker accounts.")
        return redirect_by_role(request.user)
    
    if request.method == 'POST':
        form = BrokerRegistrationForm(request.POST)
        if form.is_valid():
            # FIX: Validate email doesn't already exist
            email = form.cleaned_data.get('email')
            if User.objects.filter(email=email).exists():
                messages.error(request, f"A user with email {email} already exists.")
                return render(request, 'users/admin/create_broker.html', {'form': form})
            
            user = form.save(commit=False)
            user.is_broker = True
            # Don't set password yet - let them set it via secure link
            user.set_unusable_password()
            user.is_active = False  # FIX: Inactive until email verified
            user.save()
            
            # Send invitation email with secure link
            if send_secure_invitation_email(user, 'broker', request):
                messages.success(request, f"Broker account created for {user.email} and invitation email sent.")
                # Log for audit trail
                logger.info(f"Broker account created for {user.email} by {request.user.email}")
            else:
                messages.warning(request, f"Broker account created but email sending failed. Please resend invitation.")
            
            return redirect('admin_user_management')
    else:
        form = BrokerRegistrationForm()
    
    return render(request, 'users/admin/create_broker.html', {'form': form})


def register_applicant(request):
    """Registration view for applicants with mandatory email verification and optional SMS"""
    if request.user.is_authenticated:
        return redirect_by_role(request.user)
    
    if request.method == 'POST':
        # Use the enhanced form with SMS options
        from .sms_forms import ApplicantRegistrationWithSMSForm
        form = ApplicantRegistrationWithSMSForm(request.POST)
        
        if form.is_valid():
            # Create User account
            user = form.save(commit=False)
            user.is_applicant = True
            user.set_password(form.cleaned_data['password'])
            
            # IMPORTANT: Account is ALWAYS inactive until email verification
            user.is_active = False
            user.save()
            
            # Get form data
            email = form.cleaned_data['email']
            first_name = form.cleaned_data.get('first_name', '')
            last_name = form.cleaned_data.get('last_name', '')
            sms_opt_in = form.cleaned_data.get('sms_opt_in', False)
            verify_phone = form.cleaned_data.get('verify_phone', False)
            phone_number = form.cleaned_data.get('phone_number')
            tcpa_consent = form.cleaned_data.get('tcpa_consent', False)
            
            # Store registration data in session for after verification
            request.session['pending_registration'] = {
                'user_id': user.id,
                'email': email,
                'phone_number': phone_number,
                'sms_opt_in': sms_opt_in,
                'verify_phone': verify_phone,
                'tcpa_consent': tcpa_consent,
                'first_name': first_name,
                'last_name': last_name,
                'password': form.cleaned_data['password']  # For auto-login after verification
            }
            
            # Create or update Applicant profile
            from applicants.models import Applicant
            from django.utils import timezone
            
            applicant, created = Applicant.objects.get_or_create(
                _email=user.email,
                defaults={
                    'first_name': form.cleaned_data.get('first_name', ''),
                    'last_name': form.cleaned_data.get('last_name', ''),
                    'phone_number': phone_number or '',
                    # 'date_of_birth': timezone.now().date(),  <-- REMOVED: Invalid default
                    'street_address_1': '',
                    'city': '',
                    'state': 'NY',
                    'zip_code': '',
                }
            )
            
            # Link the applicant profile to the user account
            applicant.user = user
            if not created:
                applicant.first_name = form.cleaned_data.get('first_name', applicant.first_name)
                applicant.last_name = form.cleaned_data.get('last_name', applicant.last_name)
                if phone_number:
                    applicant.phone_number = phone_number
            applicant.save()
            
            # Create SMS preferences if phone provided
            if phone_number:
                from .sms_models import SMSPreferences
                sms_prefs, _ = SMSPreferences.objects.get_or_create(
                    user=user,
                    defaults={
                        'phone_number': phone_number,
                        'sms_enabled': sms_opt_in,
                        'tcpa_consent': tcpa_consent,
                        'tcpa_consent_date': timezone.now() if tcpa_consent else None,
                        'tcpa_consent_ip': request.META.get('REMOTE_ADDR') if tcpa_consent else None
                    }
                )

            # Send email verification
            from .email_verification import send_email_verification
            success, message = send_email_verification(email, user, purpose='registration')
            
            if success:
                request.session['pending_email_verification'] = email
                messages.info(request, "We've sent a verification code to your email. Please check your inbox and enter the code to continue.")
                return redirect('email_verification', email=email)
            else:
                # CRITICAL FIX: Do NOT delete the user if email sending fails.
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to send verification email to {email}: {message}")
                
                request.session['pending_email_verification'] = email
                messages.warning(request, "Account created, but we couldn't send the verification email right now. Please try resending it from the verification page.")
                return redirect('email_verification', email=email)
    else:
        from .sms_forms import ApplicantRegistrationWithSMSForm
        form = ApplicantRegistrationWithSMSForm()
    
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
            user.set_unusable_password()
            user.save()
            
            # Send secure invitation email
            send_secure_invitation_email(user, 'staff', request)
            
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
            user.set_unusable_password()
            user.save()
            
            # Send secure invitation email
            send_secure_invitation_email(user, 'owner', request)
            
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
    """Enhanced Dashboard for brokers with profile and metrics"""
    if not request.user.is_broker and not request.user.is_superuser:
        messages.error(request, "Access denied. Broker privileges required.")
        return redirect_by_role(request.user)
    
    # Get broker profile for personalization
    from .profiles_models import BrokerProfile
    try:
        broker_profile = BrokerProfile.objects.get(user=request.user)
    except BrokerProfile.DoesNotExist:
        broker_profile = None
    
    # Get broker's assigned buildings and apartments
    from buildings.models import Building
    from apartments.models import Apartment
    from applications.models import Application
    from datetime import datetime, timedelta
    from django.utils import timezone
    
    # Get buildings assigned to this broker
    assigned_buildings = request.user.buildings.all().prefetch_related('apartments', 'apartments__images')
    
    # Get all apartments from assigned buildings
    assigned_apartments = Apartment.objects.filter(
        building__in=assigned_buildings
    ).select_related('building').prefetch_related('images', 'building__images')
    
    # FIX: Calculate smart matches efficiently with a single query instead of O(N*M) loop
    from applicants.models import Applicant
    from django.db.models import Count, Q
    
    # Build a dictionary of match counts in ONE query
    apartment_match_counts = {}
    
    if assigned_apartments:
        # For each apartment, count matching applicants efficiently
        for apartment in assigned_apartments:
            # Simple count query - much faster than calling matching function for every applicant
            match_count = Applicant.objects.filter(
                Q(max_rent_budget__gte=apartment.rent_price) | Q(max_rent_budget__isnull=True),
                desired_move_in_date__isnull=False
            ).filter(
                # Additional basic compatibility checks - FIX: use min/max_bedrooms
                Q(min_bedrooms__lte=apartment.bedrooms) | Q(min_bedrooms__isnull=True),
                Q(max_bedrooms__gte=apartment.bedrooms) | Q(max_bedrooms__isnull=True)
            ).count()
            
            apartment.smart_matches_count = match_count
    else:
        # No apartments, set count to 0
        for apartment in assigned_apartments:
            apartment.smart_matches_count = 0
    
    # Get broker's assigned applicants with profile completion
    from applicants.apartment_matching import get_apartment_matches_for_applicant
    assigned_applicants = Applicant.objects.filter(assigned_broker=request.user)
    
    # Calculate profile completion and matches for each applicant
    for applicant in assigned_applicants:
        # Calculate profile completion percentage
        required_fields = [
            applicant.first_name,
            applicant.last_name,
            applicant.email,
            applicant.phone_number,
            applicant.date_of_birth,
            applicant.max_rent_budget,
            applicant.desired_move_in_date,
        ]
        completed = sum(1 for field in required_fields if field)
        applicant.profile_completion = int((completed / len(required_fields)) * 100)
        
        # Check if can calculate matches
        applicant.can_match = bool(applicant.max_rent_budget and applicant.desired_move_in_date)
        
        # Get match count if profile allows
        if applicant.can_match:
            try:
                matches = get_apartment_matches_for_applicant(applicant, limit=10)
                applicant.match_count = len(matches)
                applicant.top_matches = matches[:3] if matches else []
            except:
                applicant.match_count = 0
                applicant.top_matches = []
        else:
            applicant.match_count = 0
            applicant.top_matches = []
    
    # Get applications for broker's apartments only
    broker_apartment_ids = assigned_apartments.values_list('id', flat=True)
    recent_applications = Application.objects.filter(
        apartment_id__in=broker_apartment_ids
    ).select_related('applicant', 'apartment', 'apartment__building').order_by('-created_at')[:10]
    
    # Calculate broker metrics
    total_applications = Application.objects.filter(broker=request.user).count()
    
    # Applications this month
    current_month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    monthly_applications = Application.objects.filter(
        broker=request.user,
        created_at__gte=current_month_start
    ).count()
    
    # Pending applications needing attention
    pending_applications = Application.objects.filter(
        broker=request.user,
        status__in=['NEW', 'PENDING', 'IN_PROGRESS']
    ).count()
    
    # Calculate potential commission (if profile has commission rate)
    potential_commission = 0
    if broker_profile and broker_profile.standard_commission_rate:
        for apt in assigned_apartments:
            if apt.rent_price:
                # Assuming first month's rent as commission base
                potential_commission += float(apt.rent_price * broker_profile.standard_commission_rate / 100)
    
    context = {
        'user': request.user,
        'broker_profile': broker_profile,
        'assigned_buildings': assigned_buildings,
        'assigned_apartments': assigned_apartments,
        'assigned_applicants': assigned_applicants,  # ADD THIS
        'recent_applications': recent_applications,
        'total_applications': total_applications,
        'monthly_applications': monthly_applications,
        'pending_applications': pending_applications,
        'potential_commission': potential_commission,
    }
    # Use the original template for consistent styling with applicant dashboard
    template = 'users/dashboards/broker_dashboard.html'
    return render(request, template, context)


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
        
        # Only show applications that are ready for applicant action (not NEW/draft status)
        applications = Application.objects.filter(
            applicant=applicant
        ).exclude(
            status__in=['draft', 'NEW']  # Hide drafts and NEW applications from applicants
        ).order_by('-created_at')
        
        # Get profile completion status - using comprehensive field tracking
        completion_status = applicant.get_field_completion_status()
        completion_percentage = completion_status['overall']['overall_completion_percentage']

        # Build missing fields list from sections
        missing_fields = {}
        for section_name, section_data in completion_status['sections'].items():
            section_missing = [
                field_data['label'] 
                for field_name, field_data in section_data['fields'].items() 
                if not field_data['filled']
            ]
            if section_missing:
                missing_fields[section_name] = section_missing

        # Get next steps (keep using ProfileProgressService for this)
        next_steps = ProfileProgressService.get_next_profile_steps(applicant)
                
        # Always try to get apartment matches
        apartment_matches = []
        can_show_matches = bool(applicant.max_rent_budget and applicant.desired_move_in_date)

        if can_show_matches:
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
        'can_show_matches': can_show_matches,
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


def send_secure_invitation_email(user, role, request=None):
    """Send invitation email with secure token link instead of password"""
    try:
        subject = f"Welcome to Doorway - Your {role.title()} Account"
        
        # Generate secure invitation link
        invitation_link = generate_invitation_link(user, request)
        
        # Create the email context
        context = {
            'user': user,
            'role': role.title(),
            'invitation_link': invitation_link,
            'expiry_hours': 48,  # Link expires in 48 hours
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
        logger.error(f"Failed to send invitation email to {user.email}: {e}")
        return False


def set_password_view(request, uidb64, token):
    """
    Secure password setting view using tokens instead of temp passwords.
    Business Impact: More secure than sending passwords via email.
    """
    # Verify token
    user = verify_token(uidb64, token, invitation_token)
    if user is None:
        messages.error(request, 'Invalid or expired invitation link.')
        return redirect('login')
    
    if request.method == 'POST':
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        if not password or len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
        elif password != password_confirm:
            messages.error(request, 'Passwords do not match.')
        else:
            # Set password and activate user
            user.set_password(password)
            user.is_active = True
            user.save()
            
            # Log them in
            login(request, user)
            
            messages.success(request, 'Password set successfully! Welcome to DoorWay.')
            return redirect_by_role(user)
    
    return render(request, 'users/set_password.html', {
        'user': user,
        'uidb64': uidb64,
        'token': token
    })


def activate_account_view(request, uidb64, token):
    """
    Account activation view for email verification.
    """
    # Verify token
    user = verify_token(uidb64, token, account_activation_token)
    if user is None:
        messages.error(request, 'Invalid or expired activation link.')
        return redirect('login')
    
    if user.is_active:
        messages.info(request, 'Account is already activated.')
        return redirect('login')
    
    # Activate the user
    user.is_active = True
    user.save()
    
    messages.success(request, 'Account activated successfully! You can now log in.')
    return redirect('login')


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
            # Create user with unusable password (secure approach)
            user = User.objects.create_user(
                email=email
            )
            user.set_unusable_password()
            
            # Set role
            if account_type == 'broker':
                user.is_broker = True
            elif account_type == 'staff':
                user.is_staff = True
            elif account_type == 'owner':
                user.is_owner = True
            
            user.save()
            
            # Send secure invitation email
            if send_secure_invitation_email(user, account_type, request):
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
