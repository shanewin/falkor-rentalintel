from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .profiles_models import BrokerProfile, OwnerProfile, StaffProfile, AdminProfile
from .profile_forms import BrokerProfileForm, OwnerProfileForm, StaffProfileForm, AdminProfileForm
from applications.services import ProfileProgressService


@login_required
def broker_progressive_profile(request):
    """
    Progressive profile completion for brokers
    Shows completion percentage and guides users through missing fields
    """
    if not request.user.is_broker:
        messages.error(request, "Access denied. This page is for brokers only.")
        return redirect('home')
    
    # Get or create broker profile linked to user
    try:
        broker_profile = request.user.broker_profile
    except BrokerProfile.DoesNotExist:
        # Create broker profile if it doesn't exist
        broker_profile = BrokerProfile.objects.create(
            user=request.user,
            first_name='',
            last_name='',
            phone_number='',
            business_name='',
            business_address_1='',
            business_city='',
            business_zip='',
            broker_license_number='',
            license_state='NY',
            job_title='Real Estate Broker',
            years_experience=0
        )
    
    # Calculate profile completion
    completion_percentage, missing_fields = ProfileProgressService.calculate_broker_profile_completion(broker_profile)
    next_steps = ProfileProgressService.get_next_broker_profile_steps(broker_profile)
    
    if request.method == 'POST':
        form = BrokerProfileForm(request.POST, request.FILES, instance=broker_profile)
        if form.is_valid():
            with transaction.atomic():
                broker_profile = form.save()
                
                # Recalculate completion after save
                new_percentage, _ = ProfileProgressService.calculate_broker_profile_completion(broker_profile)
                
                if new_percentage == 100:
                    messages.success(request, "Congratulations! Your broker profile is now complete.")
                elif new_percentage > completion_percentage:
                    messages.success(request, f"Great progress! Your profile is now {new_percentage}% complete.")
                else:
                    messages.success(request, "Profile updated successfully.")
                
                return redirect('broker_progressive_profile')
    else:
        form = BrokerProfileForm(instance=broker_profile)
    
    # Organize form fields by section for better UX
    sections = {
        'Personal Information': ['first_name', 'last_name', 'phone_number', 'mobile_phone', 'professional_email'],
        'Business Information': ['business_name', 'business_address_1', 'business_address_2', 'business_city', 'business_state', 'business_zip'],
        'License Information': ['broker_license_number', 'license_state', 'license_expiration', 'years_experience'],
        'Professional Details': ['department', 'job_title', 'specializations', 'territories', 'standard_commission_rate', 'commission_split'],
        'Professional Information': ['bio', 'certifications', 'awards'],
        'Contact & Availability': ['preferred_contact_method', 'available_hours', 'linkedin_url', 'website_url'],
    }
    
    context = {
        'form': form,
        'profile': broker_profile,
        'completion_percentage': completion_percentage,
        'missing_fields': missing_fields,
        'next_steps': next_steps,
        'sections': sections,
        'profile_type': 'Broker',
    }
    
    return render(request, 'users/progressive_profile.html', context)


@login_required
def owner_progressive_profile(request):
    """
    Progressive profile completion for owners
    Shows completion percentage and guides users through missing fields
    """
    if not request.user.is_owner:
        messages.error(request, "Access denied. This page is for property owners only.")
        return redirect('home')
    
    # Get or create owner profile linked to user
    try:
        owner_profile = request.user.owner_profile
    except OwnerProfile.DoesNotExist:
        # Create owner profile if it doesn't exist
        owner_profile = OwnerProfile.objects.create(
            user=request.user,
            first_name='',
            last_name='',
            primary_phone='',
            address_1='',
            city='',
            zip_code='',
            number_of_properties=0,
            total_units=0,
            years_as_owner=0
        )
    
    # Calculate profile completion
    completion_percentage, missing_fields = ProfileProgressService.calculate_owner_profile_completion(owner_profile)
    next_steps = ProfileProgressService.get_next_owner_profile_steps(owner_profile)
    
    if request.method == 'POST':
        form = OwnerProfileForm(request.POST, request.FILES, instance=owner_profile)
        if form.is_valid():
            with transaction.atomic():
                owner_profile = form.save()
                
                # Recalculate completion after save
                new_percentage, _ = ProfileProgressService.calculate_owner_profile_completion(owner_profile)
                
                if new_percentage == 100:
                    messages.success(request, "Congratulations! Your owner profile is now complete.")
                elif new_percentage > completion_percentage:
                    messages.success(request, f"Great progress! Your profile is now {new_percentage}% complete.")
                else:
                    messages.success(request, "Profile updated successfully.")
                
                return redirect('owner_progressive_profile')
    else:
        form = OwnerProfileForm(instance=owner_profile)
    
    # Organize form fields by section for better UX
    sections = {
        'Owner Information': ['owner_type', 'first_name', 'last_name', 'company_name'],
        'Contact Information': ['primary_phone', 'secondary_phone', 'business_email'],
        'Primary Address': ['address_1', 'address_2', 'city', 'state', 'zip_code'],
        'Mailing Address': ['mailing_same_as_primary', 'mailing_address_1', 'mailing_address_2', 'mailing_city', 'mailing_state', 'mailing_zip'],
        'Property Portfolio': ['number_of_properties', 'total_units', 'portfolio_value', 'years_as_owner', 'acquisition_method'],
        'Property Management': ['management_style', 'management_company_name'],
        'Tax & Insurance': ['tax_id_number', 'tax_classification', 'insurance_carrier', 'insurance_policy_number', 'insurance_expiration'],
        'Banking Information': ['bank_name', 'bank_account_type'],
        'Contact Preferences': ['preferred_contact_method', 'preferred_contact_time'],
        'Emergency & Professional Contacts': ['emergency_contact_name', 'emergency_contact_phone', 'attorney_name', 'attorney_phone', 'accountant_name', 'accountant_phone'],
        'Additional Information': ['notes', 'special_instructions'],
    }
    
    context = {
        'form': form,
        'profile': owner_profile,
        'completion_percentage': completion_percentage,
        'missing_fields': missing_fields,
        'next_steps': next_steps,
        'sections': sections,
        'profile_type': 'Property Owner',
    }
    
    return render(request, 'users/progressive_profile.html', context)


@login_required
def staff_progressive_profile(request):
    """
    Progressive profile completion for staff members
    Shows completion percentage and guides users through missing fields
    """
    if not request.user.is_staff:
        messages.error(request, "Access denied. This page is for staff members only.")
        return redirect('home')
    
    # Get or create staff profile linked to user
    try:
        staff_profile = request.user.staff_profile
    except StaffProfile.DoesNotExist:
        # Create staff profile if it doesn't exist
        staff_profile = StaffProfile.objects.create(
            user=request.user,
            first_name='',
            last_name='',
            office_phone='',
            department='admin',
            job_title='',
            employment_start_date='2024-01-01',
            primary_responsibilities=''
        )
    
    # Calculate profile completion
    completion_percentage, missing_fields = ProfileProgressService.calculate_staff_profile_completion(staff_profile)
    next_steps = ProfileProgressService.get_next_staff_profile_steps(staff_profile)
    
    if request.method == 'POST':
        form = StaffProfileForm(request.POST, request.FILES, instance=staff_profile)
        if form.is_valid():
            with transaction.atomic():
                staff_profile = form.save()
                
                # Recalculate completion after save
                new_percentage, _ = ProfileProgressService.calculate_staff_profile_completion(staff_profile)
                
                if new_percentage == 100:
                    messages.success(request, "Congratulations! Your staff profile is now complete.")
                elif new_percentage > completion_percentage:
                    messages.success(request, f"Great progress! Your profile is now {new_percentage}% complete.")
                else:
                    messages.success(request, "Profile updated successfully.")
                
                return redirect('staff_progressive_profile')
    else:
        form = StaffProfileForm(instance=staff_profile)
    
    # Organize form fields by section for better UX
    sections = {
        'Personal Information': ['first_name', 'last_name', 'employee_id'],
        'Employment Information': ['employment_start_date', 'employment_type', 'department', 'job_title'],
        'Contact Information': ['office_phone', 'office_extension', 'mobile_phone', 'office_email'],
        'Office Location': ['office_building', 'office_floor', 'office_room', 'office_address_1', 'office_address_2', 'office_city', 'office_state', 'office_zip'],
        'Access & Permissions': ['access_level', 'system_permissions'],
        'Responsibilities': ['primary_responsibilities', 'secondary_responsibilities'],
        'Professional Information': ['bio', 'skills', 'certifications'],
        'Emergency Contact': ['emergency_contact_name', 'emergency_contact_relationship', 'emergency_contact_phone'],
        'Work Schedule & Training': ['work_schedule', 'remote_work_allowed', 'training_completed', 'training_required'],
    }
    
    context = {
        'form': form,
        'profile': staff_profile,
        'completion_percentage': completion_percentage,
        'missing_fields': missing_fields,
        'next_steps': next_steps,
        'sections': sections,
        'profile_type': 'Staff',
    }
    
    return render(request, 'users/progressive_profile.html', context)


@login_required
def quick_broker_profile_update(request):
    """
    Quick profile update focusing only on missing required fields for brokers
    """
    if not request.user.is_broker:
        messages.error(request, "Access denied.")
        return redirect('home')
        
    try:
        broker_profile = request.user.broker_profile
    except BrokerProfile.DoesNotExist:
        return redirect('broker_progressive_profile')
    
    # Get missing fields
    _, missing_fields = ProfileProgressService.calculate_broker_profile_completion(broker_profile)
    
    if not missing_fields:
        messages.info(request, "Your broker profile is complete!")
        return redirect('broker_dashboard')
    
    # Create a form with only missing fields
    if request.method == 'POST':
        form = BrokerProfileForm(request.POST, request.FILES, instance=broker_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated! Keep going to complete it.")
            return redirect('quick_broker_profile_update')
    else:
        form = BrokerProfileForm(instance=broker_profile)
    
    # Focus on first missing section
    focus_section = list(missing_fields.keys())[0] if missing_fields else None
    focus_fields = missing_fields.get(focus_section, []) if focus_section else []
    
    context = {
        'form': form,
        'profile': broker_profile,
        'focus_section': focus_section,
        'focus_fields': focus_fields,
        'total_missing': sum(len(fields) for fields in missing_fields.values()),
        'profile_type': 'Broker',
    }
    
    return render(request, 'users/quick_profile_update.html', context)


@login_required
def quick_owner_profile_update(request):
    """
    Quick profile update focusing only on missing required fields for owners
    """
    if not request.user.is_owner:
        messages.error(request, "Access denied.")
        return redirect('home')
        
    try:
        owner_profile = request.user.owner_profile
    except OwnerProfile.DoesNotExist:
        return redirect('owner_progressive_profile')
    
    # Get missing fields
    _, missing_fields = ProfileProgressService.calculate_owner_profile_completion(owner_profile)
    
    if not missing_fields:
        messages.info(request, "Your owner profile is complete!")
        return redirect('owner_dashboard')
    
    # Create a form with only missing fields
    if request.method == 'POST':
        form = OwnerProfileForm(request.POST, request.FILES, instance=owner_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated! Keep going to complete it.")
            return redirect('quick_owner_profile_update')
    else:
        form = OwnerProfileForm(instance=owner_profile)
    
    # Focus on first missing section
    focus_section = list(missing_fields.keys())[0] if missing_fields else None
    focus_fields = missing_fields.get(focus_section, []) if focus_section else []
    
    context = {
        'form': form,
        'profile': owner_profile,
        'focus_section': focus_section,
        'focus_fields': focus_fields,
        'total_missing': sum(len(fields) for fields in missing_fields.values()),
        'profile_type': 'Owner',
    }
    
    return render(request, 'users/quick_profile_update.html', context)


@login_required
def quick_staff_profile_update(request):
    """
    Quick profile update focusing only on missing required fields for staff
    """
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect('home')
        
    try:
        staff_profile = request.user.staff_profile
    except StaffProfile.DoesNotExist:
        return redirect('staff_progressive_profile')
    
    # Get missing fields
    _, missing_fields = ProfileProgressService.calculate_staff_profile_completion(staff_profile)
    
    if not missing_fields:
        messages.info(request, "Your staff profile is complete!")
        return redirect('staff_dashboard')
    
    # Create a form with only missing fields
    if request.method == 'POST':
        form = StaffProfileForm(request.POST, request.FILES, instance=staff_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated! Keep going to complete it.")
            return redirect('quick_staff_profile_update')
    else:
        form = StaffProfileForm(instance=staff_profile)
    
    # Focus on first missing section
    focus_section = list(missing_fields.keys())[0] if missing_fields else None
    focus_fields = missing_fields.get(focus_section, []) if focus_section else []
    
    context = {
        'form': form,
        'profile': staff_profile,
        'focus_section': focus_section,
        'focus_fields': focus_fields,
        'total_missing': sum(len(fields) for fields in missing_fields.values()),
        'profile_type': 'Staff',
    }
    
    return render(request, 'users/quick_profile_update.html', context)


@login_required
def admin_progressive_profile(request):
    """
    Progressive profile completion for admin users (superusers)
    Shows completion percentage and guides users through missing fields
    """
    if not request.user.is_superuser:
        messages.error(request, "Access denied. This page is for administrators only.")
        return redirect('home')
    
    # Get or create admin profile linked to user
    try:
        admin_profile = request.user.admin_profile
    except AdminProfile.DoesNotExist:
        # Create admin profile if it doesn't exist
        admin_profile = AdminProfile.objects.create(
            user=request.user,
            first_name='',
            last_name='',
            phone_number='',
            title='System Administrator',
            admin_level='system',
            responsibilities=''
        )
    
    # Calculate profile completion
    completion_percentage, missing_fields = ProfileProgressService.calculate_admin_profile_completion(admin_profile)
    next_steps = ProfileProgressService.get_next_admin_profile_steps(admin_profile)
    
    if request.method == 'POST':
        form = AdminProfileForm(request.POST, request.FILES, instance=admin_profile)
        if form.is_valid():
            with transaction.atomic():
                admin_profile = form.save()
                
                # Recalculate completion after save
                new_percentage, _ = ProfileProgressService.calculate_admin_profile_completion(admin_profile)
                
                if new_percentage == 100:
                    messages.success(request, "Congratulations! Your admin profile is now complete.")
                elif new_percentage > completion_percentage:
                    messages.success(request, f"Great progress! Your profile is now {new_percentage}% complete.")
                else:
                    messages.success(request, "Profile updated successfully.")
                
                return redirect('admin_progressive_profile')
    else:
        form = AdminProfileForm(instance=admin_profile)
    
    # Organize form fields by section for better UX
    sections = {
        'Personal Information': ['first_name', 'last_name', 'title', 'phone_number', 'mobile_phone', 'admin_email'],
        'Administrative Access': ['admin_level', 'system_access_level', 'departments_managed', 'buildings_managed', 'user_groups_managed'],
        'System Permissions': ['can_create_users', 'can_modify_system_settings', 'can_access_logs', 'can_manage_backups', 'can_manage_integrations', 'can_view_financial_data', 'can_manage_notifications'],
        'Security & Monitoring': ['two_factor_enabled', 'security_clearance_level', 'security_clearance_expiry', 'last_security_review', 'compliance_training_date'],
        'Contact & Availability': ['preferred_contact_method', 'availability_hours', 'on_call_schedule', 'escalation_contact'],
        'Emergency Contacts': ['emergency_contact_name', 'emergency_contact_relationship', 'emergency_contact_phone', 'backup_admin_contact', 'backup_admin_phone'],
        'Professional Information': ['bio', 'technical_skills', 'certifications', 'specializations'],
        'Work Location & Remote Access': ['primary_work_location', 'remote_work_setup', 'vpn_access_required'],
        'Administrative Documentation': ['responsibilities', 'system_knowledge', 'critical_contacts', 'notes'],
    }
    
    context = {
        'form': form,
        'profile': admin_profile,
        'completion_percentage': completion_percentage,
        'missing_fields': missing_fields,
        'next_steps': next_steps,
        'sections': sections,
        'profile_type': 'Administrator',
    }
    
    return render(request, 'users/progressive_profile.html', context)


@login_required
def quick_admin_profile_update(request):
    """
    Quick profile update focusing only on missing required fields for admins
    """
    if not request.user.is_superuser:
        messages.error(request, "Access denied.")
        return redirect('home')
        
    try:
        admin_profile = request.user.admin_profile
    except AdminProfile.DoesNotExist:
        return redirect('admin_progressive_profile')
    
    # Get missing fields
    _, missing_fields = ProfileProgressService.calculate_admin_profile_completion(admin_profile)
    
    if not missing_fields:
        messages.info(request, "Your admin profile is complete!")
        return redirect('admin_dashboard')
    
    # Create a form with only missing fields
    if request.method == 'POST':
        form = AdminProfileForm(request.POST, request.FILES, instance=admin_profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated! Keep going to complete it.")
            return redirect('quick_admin_profile_update')
    else:
        form = AdminProfileForm(instance=admin_profile)
    
    # Focus on first missing section
    focus_section = list(missing_fields.keys())[0] if missing_fields else None
    focus_fields = missing_fields.get(focus_section, []) if focus_section else []
    
    context = {
        'form': form,
        'profile': admin_profile,
        'focus_section': focus_section,
        'focus_fields': focus_fields,
        'total_missing': sum(len(fields) for fields in missing_fields.values()),
        'profile_type': 'Administrator',
    }
    
    return render(request, 'users/quick_profile_update.html', context)