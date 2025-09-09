"""
Service functions for intelligent application pre-filling and data management
"""
from django.contrib.auth import authenticate, login
from django.db import transaction
from applicants.models import Applicant
from users.models import User
from .models import Application, PersonalInfoData


class ApplicationDataService:
    """Service for managing application data and pre-filling"""
    
    @staticmethod
    def get_prefill_data_for_applicant(applicant):
        """
        Get pre-fill data from applicant profile and their previous applications
        Returns a dictionary with form field names and values
        """
        if not applicant:
            return {}
        
        prefill_data = {
            # Basic Info
            'first_name': applicant.first_name,
            'last_name': applicant.last_name,
            'email': applicant.email,
            'phone_number': applicant.phone_number,
            'date_of_birth': applicant.date_of_birth,
            
            # Current Address
            'street_address_1': applicant.street_address_1,
            'street_address_2': applicant.street_address_2,
            'city': applicant.city,
            'state': applicant.state,
            'zip_code': applicant.zip_code,
            
            # Housing Info
            'length_at_current_address': applicant.length_at_current_address,
            'housing_status': applicant.housing_status,
            'current_landlord_name': applicant.current_landlord_name,
            'current_landlord_phone': applicant.current_landlord_phone,
            'current_landlord_email': applicant.current_landlord_email,
            'reason_for_moving': applicant.reason_for_moving,
            'monthly_rent': applicant.monthly_rent,
            
            # ID
            'driver_license_number': applicant.driver_license_number,
            'driver_license_state': applicant.driver_license_state,
            
            # Employment Status & Fields
            'employment_status': applicant.employment_status,
            'company_name': applicant.company_name,
            'position': applicant.position,
            'annual_income': applicant.annual_income,
            'supervisor_name': applicant.supervisor_name,
            'supervisor_email': applicant.supervisor_email,
            'supervisor_phone': applicant.supervisor_phone,
            'currently_employed': applicant.currently_employed,
            'employment_start_date': applicant.employment_start_date,
            'employment_end_date': applicant.employment_end_date,
            
            # Student Fields
            'school_name': applicant.school_name,
            'year_of_graduation': applicant.year_of_graduation,
            'school_address': applicant.school_address,
            'school_phone': applicant.school_phone,
            
            # Employment fields
            'company_name': applicant.company_name,
            'position': applicant.position,
            'annual_income': applicant.annual_income,
            'supervisor_name': applicant.supervisor_name,
            'supervisor_email': applicant.supervisor_email,
            
            # Emergency Contact
            'emergency_contact_name': applicant.emergency_contact_name,
            'emergency_contact_relationship': applicant.emergency_contact_relationship,
            'emergency_contact_phone': applicant.emergency_contact_phone,
            
            # Additional housing fields
            'length_at_current_address': applicant.length_at_current_address,
            'reason_for_moving': applicant.reason_for_moving,
        }
        
        # Get data from most recent completed application if available
        recent_app = Application.objects.filter(
            applicant=applicant,
            submitted_by_applicant=True
        ).order_by('-created_at').first()
        
        if recent_app:
            # Try to get PersonalInfoData from recent application
            try:
                personal_info = PersonalInfoData.objects.filter(
                    application=recent_app
                ).first()
                
                if personal_info:
                    # Update with more recent data if available
                    if personal_info.ssn_encrypted:
                        prefill_data['ssn_last_four'] = '****'  # Indicate SSN is on file
                    if personal_info.employment_type:
                        prefill_data['employment_type'] = personal_info.employment_type
            except PersonalInfoData.DoesNotExist:
                pass
        
        # Remove None values
        return {k: v for k, v in prefill_data.items() if v is not None}
    
    @staticmethod
    def update_applicant_from_application(applicant, application_data):
        """
        Update applicant profile with data from completed application
        Only updates fields that are empty in the profile
        """
        if not applicant:
            return
        
        # Map of application field names to applicant field names
        field_mapping = {
            'first_name': 'first_name',
            'last_name': 'last_name',
            'phone_number': 'phone_number',
            'street_address_1': 'street_address_1',
            'street_address_2': 'street_address_2',
            'city': 'city',
            'state': 'state',
            'zip_code': 'zip_code',
            'company_name': 'company_name',
            'position': 'position',
            'annual_income': 'annual_income',
            'driver_license_number': 'driver_license_number',
            'driver_license_state': 'driver_license_state',
        }
        
        updated_fields = []
        for app_field, profile_field in field_mapping.items():
            if app_field in application_data and application_data[app_field]:
                current_value = getattr(applicant, profile_field, None)
                if not current_value:  # Only update if field is empty
                    setattr(applicant, profile_field, application_data[app_field])
                    updated_fields.append(profile_field)
        
        if updated_fields:
            applicant.save(update_fields=updated_fields)
        
        return updated_fields


class AccountCreationService:
    """Service for creating user accounts from completed applications"""
    
    @staticmethod
    @transaction.atomic
    def create_account_from_application(email, password, application=None):
        """
        Create a user account from a completed application
        Links the account to existing applicant profile
        """
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            return None, "An account with this email already exists"
        
        # Create user account
        user = User.objects.create_user(
            email=email,
            password=password,
            is_applicant=True
        )
        
        # Find or create applicant profile
        try:
            applicant = Applicant.objects.get(email=email)
            applicant.user = user
            applicant.save()
            
            # If we have an application, update applicant with its data
            if application:
                from applications.forms import PersonalInfoForm
                personal_info = PersonalInfoData.objects.filter(
                    application=application
                ).first()
                
                if personal_info:
                    # Update applicant profile with application data
                    ApplicationDataService.update_applicant_from_application(
                        applicant,
                        {
                            'first_name': personal_info.first_name,
                            'last_name': personal_info.last_name,
                            'phone_number': personal_info.phone_number,
                            # Add more fields as needed
                        }
                    )
            
        except Applicant.DoesNotExist:
            # This shouldn't happen if application was completed properly
            pass
        
        return user, None
    
    @staticmethod
    def link_anonymous_applications(user):
        """
        Link any anonymous applications to the newly created user account
        Based on email matching
        """
        if not user or not user.email:
            return []
        
        # Find applicant profile
        try:
            applicant = Applicant.objects.get(email=user.email)
            
            # Find applications without linked users but with matching applicant
            anonymous_apps = Application.objects.filter(
                applicant=applicant,
                broker__isnull=True  # Anonymous applications
            )
            
            # Update applications to link to user
            count = anonymous_apps.update(broker=user)
            
            return anonymous_apps
            
        except Applicant.DoesNotExist:
            return []


class ProfileProgressService:
    """Service for managing progressive profile completion"""
    
    @staticmethod
    def calculate_profile_completion(applicant):
        """
        Calculate the completion percentage of an applicant profile
        Returns percentage and list of missing required fields
        """
        if not applicant:
            return 0, []
        
        # Define required fields and their weights - matching profile form sections
        required_fields = {
            'Basic Info': [
                ('first_name', 1),
                ('last_name', 1),
                ('email', 1),
                ('phone_number', 1),
                ('date_of_birth', 2),
            ],
            'Address': [
                ('street_address_1', 2),
                ('city', 1),
                ('state', 1),
                ('zip_code', 1),
            ],
            'Housing Preferences': [
                ('desired_move_in_date', 1),
                ('number_of_bedrooms', 1),
                ('number_of_bathrooms', 1),
                ('max_rent_budget', 2),
            ],
            'Employment': [
                ('company_name', 2),
                ('annual_income', 2),
                ('position', 1),
            ],
        }
        
        total_weight = 0
        completed_weight = 0
        missing_fields = {}
        
        for section, fields in required_fields.items():
            section_missing = []
            for field_name, weight in fields:
                total_weight += weight
                value = getattr(applicant, field_name, None)
                
                # Check if field has a value - handle ManyToMany fields differently
                has_value = False
                if hasattr(applicant, field_name):
                    field_obj = getattr(applicant, field_name)
                    if hasattr(field_obj, 'exists'):  # ManyToMany field
                        has_value = field_obj.exists()
                    elif value:  # Regular field
                        has_value = True
                
                if has_value:
                    completed_weight += weight
                else:
                    section_missing.append(field_name.replace('_', ' ').title())
            
            if section_missing:
                missing_fields[section] = section_missing
        
        percentage = int((completed_weight / total_weight * 100)) if total_weight > 0 else 0
        
        return percentage, missing_fields
    
    @staticmethod
    def get_next_profile_steps(applicant):
        """
        Get recommended next steps for profile completion
        """
        percentage, missing_fields = ProfileProgressService.calculate_profile_completion(applicant)
        
        next_steps = []
        
        if percentage < 30:
            next_steps.append("Complete your basic information")
        elif percentage < 60:
            next_steps.append("Add your employment details")
        elif percentage < 80:
            next_steps.append("Provide identification information")
        elif percentage < 100:
            next_steps.append("Fill in remaining optional fields")
        else:
            next_steps.append("Your profile is complete!")
        
        # Add specific missing field recommendations
        for section, fields in missing_fields.items():
            if len(fields) <= 3:  # Only show if few fields missing
                next_steps.append(f"Add your {', '.join(fields).lower()}")
        
        return next_steps[:3]  # Return top 3 recommendations
    
    @staticmethod
    def calculate_broker_profile_completion(broker_profile):
        """
        Calculate the completion percentage of a broker profile
        Returns percentage and list of missing required fields
        """
        if not broker_profile:
            return 0, []
        
        # Define required fields and their weights for brokers
        required_fields = {
            'Personal Information': [
                ('first_name', 2),
                ('last_name', 2),
                ('phone_number', 1),
            ],
            'Business Information': [
                ('business_name', 2),
                ('business_address_1', 2),
                ('business_city', 1),
                ('business_state', 1),
                ('business_zip', 1),
            ],
            'License Information': [
                ('broker_license_number', 3),
                ('license_state', 2),
                ('years_experience', 1),
            ],
            'Professional Details': [
                ('position', 1),
                ('preferred_contact_method', 1),
            ],
        }
        
        return ProfileProgressService._calculate_completion(broker_profile, required_fields)
    
    @staticmethod
    def calculate_owner_profile_completion(owner_profile):
        """
        Calculate the completion percentage of an owner profile
        Returns percentage and list of missing required fields
        """
        if not owner_profile:
            return 0, []
        
        # Define required fields and their weights for owners
        required_fields = {
            'Owner Information': [
                ('first_name', 2),
                ('last_name', 2),
                ('owner_type', 1),
            ],
            'Contact Information': [
                ('primary_phone', 2),
            ],
            'Primary Address': [
                ('address_1', 2),
                ('city', 1),
                ('state', 1),
                ('zip_code', 1),
            ],
            'Property Portfolio': [
                ('number_of_properties', 2),
                ('total_units', 2),
            ],
            'Property Management': [
                ('management_style', 1),
            ],
        }
        
        return ProfileProgressService._calculate_completion(owner_profile, required_fields)
    
    @staticmethod
    def calculate_staff_profile_completion(staff_profile):
        """
        Calculate the completion percentage of a staff profile
        Returns percentage and list of missing required fields
        """
        if not staff_profile:
            return 0, []
        
        # Define required fields and their weights for staff
        required_fields = {
            'Personal Information': [
                ('first_name', 2),
                ('last_name', 2),
                ('employee_id', 1),
            ],
            'Employment Information': [
                ('department', 2),
                ('position', 2),
                ('employment_start_date', 2),
                ('employment_type', 1),
            ],
            'Contact Information': [
                ('office_phone', 1),
            ],
            'Access & Permissions': [
                ('access_level', 2),
            ],
            'Responsibilities': [
                ('primary_responsibilities', 2),
            ],
        }
        
        return ProfileProgressService._calculate_completion(staff_profile, required_fields)
    
    @staticmethod
    def _calculate_completion(profile, required_fields):
        """
        Generic method to calculate completion percentage
        """
        total_weight = 0
        completed_weight = 0
        missing_fields = {}
        
        for section, fields in required_fields.items():
            section_missing = []
            for field_name, weight in fields:
                total_weight += weight
                value = getattr(profile, field_name, None)
                
                # Handle different field types
                if isinstance(value, (list, dict)) and value:
                    completed_weight += weight
                elif value and str(value).strip():
                    completed_weight += weight
                else:
                    section_missing.append(field_name.replace('_', ' ').title())
            
            if section_missing:
                missing_fields[section] = section_missing
        
        percentage = int((completed_weight / total_weight * 100)) if total_weight > 0 else 0
        
        return percentage, missing_fields
    
    @staticmethod
    def get_next_broker_profile_steps(broker_profile):
        """Get recommended next steps for broker profile completion"""
        percentage, missing_fields = ProfileProgressService.calculate_broker_profile_completion(broker_profile)
        
        next_steps = []
        
        if percentage < 30:
            next_steps.append("Complete your license information")
        elif percentage < 60:
            next_steps.append("Add your brokerage details")
        elif percentage < 80:
            next_steps.append("Fill in professional information")
        elif percentage < 100:
            next_steps.append("Complete contact and availability details")
        else:
            next_steps.append("Your broker profile is complete!")
        
        # Add specific recommendations
        for section, fields in missing_fields.items():
            if len(fields) <= 2:
                next_steps.append(f"Add your {', '.join(fields).lower()}")
        
        return next_steps[:3]
    
    @staticmethod
    def get_next_owner_profile_steps(owner_profile):
        """Get recommended next steps for owner profile completion"""
        percentage, missing_fields = ProfileProgressService.calculate_owner_profile_completion(owner_profile)
        
        next_steps = []
        
        if percentage < 30:
            next_steps.append("Complete your company information")
        elif percentage < 60:
            next_steps.append("Add your portfolio details")
        elif percentage < 80:
            next_steps.append("Fill in insurance and legal information")
        elif percentage < 100:
            next_steps.append("Complete rental policies")
        else:
            next_steps.append("Your owner profile is complete!")
        
        # Add specific recommendations
        for section, fields in missing_fields.items():
            if len(fields) <= 2:
                next_steps.append(f"Add your {', '.join(fields).lower()}")
        
        return next_steps[:3]
    
    @staticmethod
    def get_next_staff_profile_steps(staff_profile):
        """Get recommended next steps for staff profile completion"""
        percentage, missing_fields = ProfileProgressService.calculate_staff_profile_completion(staff_profile)
        
        next_steps = []
        
        if percentage < 30:
            next_steps.append("Complete your employment information")
        elif percentage < 60:
            next_steps.append("Add your office and contact details")
        elif percentage < 80:
            next_steps.append("Set up access and permissions")
        elif percentage < 100:
            next_steps.append("Add emergency contact information")
        else:
            next_steps.append("Your staff profile is complete!")
        
        # Add specific recommendations
        for section, fields in missing_fields.items():
            if len(fields) <= 2:
                next_steps.append(f"Add your {', '.join(fields).lower()}")
        
        return next_steps[:3]
    
    @staticmethod
    def calculate_admin_profile_completion(admin_profile):
        """
        Calculate the completion percentage of an admin profile
        Returns percentage and list of missing required fields
        """
        if not admin_profile:
            return 0, []
        
        # Define required fields and their weights for admins
        required_fields = {
            'Personal Information': [
                ('first_name', 2),
                ('last_name', 2),
                ('title', 1),
                ('phone_number', 2),
            ],
            'Administrative Access': [
                ('admin_level', 2),
                ('system_access_level', 2),
            ],
            'System Permissions': [
                ('can_create_users', 1),
                ('can_modify_system_settings', 1),
                ('can_access_logs', 1),
            ],
            'Contact & Availability': [
                ('preferred_contact_method', 1),
            ],
            'Administrative Documentation': [
                ('responsibilities', 3),
            ],
        }
        
        return ProfileProgressService._calculate_completion(admin_profile, required_fields)
    
    @staticmethod
    def get_next_admin_profile_steps(admin_profile):
        """Get recommended next steps for admin profile completion"""
        percentage, missing_fields = ProfileProgressService.calculate_admin_profile_completion(admin_profile)
        
        next_steps = []
        
        if percentage < 30:
            next_steps.append("Complete your personal information")
        elif percentage < 60:
            next_steps.append("Set up your administrative access levels")
        elif percentage < 80:
            next_steps.append("Configure system permissions")
        elif percentage < 100:
            next_steps.append("Complete contact and documentation")
        else:
            next_steps.append("Your admin profile is complete!")
        
        # Add specific recommendations
        for section, fields in missing_fields.items():
            if len(fields) <= 2:
                next_steps.append(f"Add your {', '.join(fields).lower()}")
        
        return next_steps[:3]