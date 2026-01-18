from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import Applicant, PreviousAddress, ApplicantJob, ApplicantIncomeSource, ApplicantAsset
from .forms import ApplicantForm, ApplicantBasicInfoForm, ApplicantHousingForm, ApplicantEmploymentForm


def _format_duration_from_dropdowns(years_str, months_str):
    """Convert dropdown values to readable duration text"""
    years = int(years_str) if years_str and years_str.isdigit() else 0
    months = int(months_str) if months_str and months_str.isdigit() else 0
    
    if years == 0 and months == 0:
        return ''
    
    parts = []
    if years > 0:
        parts.append(f"{years} year{'s' if years != 1 else ''}")
    if months > 0:
        parts.append(f"{months} month{'s' if months != 1 else ''}")
    
    return ' and '.join(parts)


def get_step_completion_status(applicant):
    """
    Check actual completion status of each step based on form fields
    """
    if not applicant:
        return {'step1': False, 'step2': False, 'step3': False}
    
    # Step 1: Basic Info - require more than just account basics
    # Check if user has filled additional info beyond account creation
    step1_complete = bool(
        applicant.first_name and applicant.last_name and applicant.email and
        (applicant.phone_number or 
         applicant.street_address_1 or 
         applicant.date_of_birth or
         applicant.emergency_contact_name)
    )
    
    # Step 2: Housing Needs - check if any housing preference fields are filled (ignoring default values)
    step2_complete = bool(
        applicant.desired_move_in_date or 
        (applicant.number_of_bedrooms and applicant.number_of_bedrooms != 1.0) or 
        (applicant.number_of_bathrooms and applicant.number_of_bathrooms != 1.0) or 
        applicant.max_rent_budget or
        applicant.amenities.exists() or
        applicant.neighborhood_preferences.exists()
    )
    
    # Step 3: Employment - check if any employment fields are filled
    step3_complete = bool(
        applicant.company_name or 
        applicant.position or 
        applicant.annual_income or 
        applicant.jobs.exists() or
        applicant.income_sources.exists()
    )
    
    return {
        'step1': step1_complete,
        'step2': step2_complete,
        'step3': step3_complete
    }


@login_required
def progressive_profile(request):
    """
    Redirects the old summary page to Step 1 of the profile.
    Notifications are now handled in-context on the step pages.
    """
    return redirect('profile_step1')


@login_required
def quick_profile_update(request):
    """
    Quick profile update focusing only on missing required fields
    """
    try:
        applicant = request.user.applicant_profile
    except Applicant.DoesNotExist:
        return redirect('progressive_profile')
    
    # Get missing fields
    completion_status = applicant.get_field_completion_status()
    missing_fields = {}
    for section_name, section_data in completion_status['sections'].items():
        section_missing = [field_data['label'] for field_name, field_data in section_data['fields'].items() if not field_data['filled']]
        if section_missing:
            missing_fields[section_name] = section_missing
    
    if not missing_fields:
        messages.info(request, "Your profile is complete!")
        return redirect('applicant_dashboard')
    
    # Create a form with only missing fields
    if request.method == 'POST':
        form = ApplicantForm(request.POST, instance=applicant)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated! Keep going to complete it.")
            return redirect('quick_profile_update')
    else:
        form = ApplicantForm(instance=applicant)
    
    # Focus on first missing section
    focus_section = list(missing_fields.keys())[0] if missing_fields else None
    focus_fields = missing_fields.get(focus_section, []) if focus_section else []
    
    context = {
        'form': form,
        'applicant': applicant,
        'focus_section': focus_section,
        'focus_fields': focus_fields,
        'total_missing': sum(len(fields) for fields in missing_fields.values()),
    }
    
    return render(request, 'applicants/quick_profile_update.html', context)


# Multi-step profile views

@login_required
def profile_step1(request):
    """
    Step 1: Basic Information
    """
    # Get or create applicant profile
    try:
        applicant = request.user.applicant_profile
    except Applicant.DoesNotExist:
        applicant = Applicant.objects.create(
            user=request.user,
            email=request.user.email,
            first_name='',
            last_name='',
        )
    
    if request.method == 'POST':
        form = ApplicantBasicInfoForm(request.POST, request.FILES, instance=applicant, request=request)
        if form.is_valid():
            with transaction.atomic():
                applicant = form.save()
                
                # Handle profile photo upload (same logic as progressive_profile)
                if 'profile_photo' in request.FILES:
                    import json
                    import base64
                    from io import BytesIO
                    from PIL import Image
                    from django.core.files.base import ContentFile
                    from .models import ApplicantPhoto
                    
                    # Remove existing photos first
                    ApplicantPhoto.objects.filter(applicant=applicant).delete()
                    
                    # Get crop data if provided
                    crop_data = request.POST.get('crop_data', '')
                    
                    if crop_data:
                        try:
                            crop_info = json.loads(crop_data)
                            
                            if crop_info.get('cropped') and crop_info.get('croppedImage'):
                                cropped_image_data = crop_info['croppedImage']
                                if cropped_image_data.startswith('data:image'):
                                    format_info, base64_data = cropped_image_data.split(';base64,')
                                    image_data = base64.b64decode(base64_data)
                                    
                                    image_file = ContentFile(image_data, name=f"profile_{applicant.id}_cropped.jpg")
                                    photo = ApplicantPhoto(applicant=applicant, image=image_file)
                                    photo.save()
                                else:
                                    photo = ApplicantPhoto(applicant=applicant, image=request.FILES['profile_photo'])
                                    photo.save()
                            else:
                                photo = ApplicantPhoto(applicant=applicant, image=request.FILES['profile_photo'])
                                photo.save()
                        except (json.JSONDecodeError, ValueError, KeyError) as e:
                            photo = ApplicantPhoto(applicant=applicant, image=request.FILES['profile_photo'])
                            photo.save()
                    else:
                        photo = ApplicantPhoto(applicant=applicant, image=request.FILES['profile_photo'])
                        photo.save()
                
                # Handle identification document uploads
                from .models import IdentificationDocument
                import base64
                from django.core.files.base import ContentFile
                
                # Helper function to process cropped image data
                def process_cropped_image(crop_data_json, original_file):
                    if crop_data_json:
                        try:
                            crop_info = json.loads(crop_data_json)
                            if crop_info.get('cropped') and crop_info.get('croppedImage'):
                                # Extract base64 image data
                                image_data = crop_info['croppedImage']
                                if 'base64,' in image_data:
                                    format, imgstr = image_data.split('base64,')
                                    ext = format.split('/')[-1].split(';')[0]
                                    # Create a ContentFile from the base64 data
                                    return ContentFile(base64.b64decode(imgstr), name=f'cropped.{ext}')
                        except Exception as e:
                            print(f"Error processing crop data: {e}")
                    return original_file
                
                # Check for passport upload
                if 'passport_document' in request.FILES:
                    crop_data = request.POST.get('crop_data_passport', '')
                    image_file = process_cropped_image(crop_data, request.FILES['passport_document'])
                    IdentificationDocument.objects.update_or_create(
                        applicant=applicant,
                        id_type='passport',
                        side='single',
                        defaults={'document_image': image_file}
                    )
                
                # Handle driver license uploads (front and back in same record)
                driver_doc, created = IdentificationDocument.objects.get_or_create(
                    applicant=applicant,
                    id_type='driver_license',
                    defaults={'side': 'front'}  # Default side, but we'll store both images
                )
                
                if 'driver_license_front' in request.FILES:
                    crop_data = request.POST.get('crop_data_driver_front', '')
                    image_file = process_cropped_image(crop_data, request.FILES['driver_license_front'])
                    driver_doc.document_image_front = image_file
                    driver_doc.save()
                
                if 'driver_license_back' in request.FILES:
                    crop_data = request.POST.get('crop_data_driver_back', '')
                    image_file = process_cropped_image(crop_data, request.FILES['driver_license_back'])
                    driver_doc.document_image_back = image_file
                    driver_doc.save()
                
                # Handle state ID uploads (front and back in same record)
                state_doc, created = IdentificationDocument.objects.get_or_create(
                    applicant=applicant,
                    id_type='state_id',
                    defaults={'side': 'front'}  # Default side, but we'll store both images
                )
                
                if 'state_id_front' in request.FILES:
                    crop_data = request.POST.get('crop_data_state_front', '')
                    image_file = process_cropped_image(crop_data, request.FILES['state_id_front'])
                    state_doc.document_image_front = image_file
                    state_doc.save()
                
                if 'state_id_back' in request.FILES:
                    crop_data = request.POST.get('crop_data_state_back', '')
                    image_file = process_cropped_image(crop_data, request.FILES['state_id_back'])
                    state_doc.document_image_back = image_file
                    state_doc.save()
                
                # Handle previous address submissions (same logic as progressive_profile)
                previous_addresses_data = []
                for i in range(1, 5):
                    street_address_1 = request.POST.get(f'prev_street_address_1_{i}', '').strip()
                    if street_address_1:
                        previous_addresses_data.append({
                            'order': i,
                            'street_address_1': street_address_1,
                            'street_address_2': request.POST.get(f'prev_street_address_2_{i}', '').strip(),
                            'city': request.POST.get(f'prev_city_{i}', '').strip(),
                            'state': request.POST.get(f'prev_state_{i}', '').strip(),
                            'zip_code': request.POST.get(f'prev_zip_code_{i}', '').strip(),
                            'length_at_address': _format_duration_from_dropdowns(
                                request.POST.get(f'prev_address_years_{i}', ''),
                                request.POST.get(f'prev_address_months_{i}', '')
                            ),
                            'years': request.POST.get(f'prev_address_years_{i}', ''),
                            'months': request.POST.get(f'prev_address_months_{i}', ''),
                            'housing_status': request.POST.get(f'prev_housing_status_{i}', 'own'),
                            'landlord_name': request.POST.get(f'prev_landlord_name_{i}', '').strip(),
                            'landlord_phone': request.POST.get(f'prev_landlord_phone_{i}', '').strip(),
                            'landlord_email': request.POST.get(f'prev_landlord_email_{i}', '').strip(),
                            'monthly_rent': request.POST.get(f'prev_monthly_rent_{i}', '').strip(),
                        })
                
                # Clear existing previous addresses and create new ones
                PreviousAddress.objects.filter(applicant=applicant).delete()
                for addr_data in previous_addresses_data:
                    PreviousAddress.objects.create(
                        applicant=applicant,
                        order=addr_data['order'],
                        street_address_1=addr_data['street_address_1'],
                        street_address_2=addr_data['street_address_2'] if addr_data['street_address_2'] else None,
                        city=addr_data['city'] if addr_data['city'] else None,
                        state=addr_data['state'] if addr_data['state'] else None,
                        zip_code=addr_data['zip_code'] if addr_data['zip_code'] else None,
                        length_at_address=addr_data['length_at_address'] if addr_data['length_at_address'] else None,
                        years=int(addr_data.get('years')) if addr_data.get('years') else 0,
                        months=int(addr_data.get('months')) if addr_data.get('months') else 0,
                        housing_status=addr_data['housing_status'],
                        landlord_name=addr_data['landlord_name'] if addr_data['landlord_name'] else None,
                        landlord_phone=addr_data['landlord_phone'] if addr_data['landlord_phone'] else None,
                        landlord_email=addr_data['landlord_email'] if addr_data['landlord_email'] else None,
                        monthly_rent=addr_data['monthly_rent'] if addr_data['monthly_rent'] else None,
                    )
                
                messages.success(request, "Basic information saved! Let's continue with your housing preferences.")
                return redirect('profile_step2')
    else:
        form = ApplicantBasicInfoForm(instance=applicant, request=request)
    
    # Get existing previous addresses
    previous_addresses = PreviousAddress.objects.filter(applicant=applicant).order_by('order')
    
    # Get existing identification documents
    from .models import IdentificationDocument
    identification_documents = IdentificationDocument.objects.filter(applicant=applicant)
    
    # Get completion status for progress bar
    completion_status = get_step_completion_status(applicant)
    
    # Calculate actual profile completion percentage using the new logic
    completion_status = applicant.get_field_completion_status()
    completion_percentage = completion_status['overall_completion_percentage']
    
    context = {
        'form': form,
        'applicant': applicant,
        'previous_addresses': previous_addresses,
        'identification_documents': identification_documents,
        'current_step': 1,
        'step_title': 'Step 1: Basic Info',
        'completion_status': completion_status,
        'completion_percentage': completion_percentage,
    }
    
    return render(request, 'applicants/profile_step1.html', context)


@login_required
def profile_step2(request):
    """
    Step 2: Housing Needs and Preferences
    """
    # Get or create applicant profile
    try:
        applicant = request.user.applicant_profile
    except Applicant.DoesNotExist:
        applicant = Applicant.objects.create(
            user=request.user,
            email=request.user.email,
            first_name='',
            last_name='',
        )
    
    if request.method == 'POST':
        form = ApplicantHousingForm(request.POST, request.FILES, instance=applicant, request=request)
        if form.is_valid():
            with transaction.atomic():
                form.save()
                
                # Handle pets data
                from .models import Pet, PetPhoto
                import base64
                from django.core.files.base import ContentFile
                
                # Helper function to process cropped image data (same as step1)
                def process_cropped_image(crop_data_json, original_file):
                    if crop_data_json:
                        try:
                            crop_info = json.loads(crop_data_json)
                            if crop_info.get('cropped') and crop_info.get('croppedImage'):
                                # Extract base64 image data
                                image_data = crop_info['croppedImage']
                                if 'base64,' in image_data:
                                    format, imgstr = image_data.split('base64,')
                                    ext = format.split('/')[-1].split(';')[0]
                                    # Create a ContentFile from the base64 data
                                    return ContentFile(base64.b64decode(imgstr), name=f'cropped.{ext}')
                        except Exception as e:
                            print(f"Error processing crop data: {e}")
                    return original_file
                
                # Clear existing pets first
                Pet.objects.filter(applicant=applicant).delete()
                
                # Check if user has pets
                has_pets = request.POST.get('has_pets') == 'on'
                
                if has_pets:
                    # Process up to 5 pets
                    for i in range(1, 6):
                        pet_type = request.POST.get(f'pet_type_{i}', '').strip()
                        pet_name = request.POST.get(f'pet_name_{i}', '').strip()
                        
                        if pet_type:  # Only create pet if type is provided
                            pet = Pet.objects.create(
                                applicant=applicant,
                                pet_type=pet_type,
                                name=pet_name if pet_name else None,
                                quantity=1,  # Default to 1
                                description=request.POST.get(f'pet_description_{i}', '').strip() or None,
                            )
                            
                            # Handle pet photo uploads (up to 3 photos per pet)
                            for photo_num in range(1, 4):
                                photo_field = f'pet_photo_{i}_{photo_num}'
                                crop_data_field = f'crop_data_pet_{i}_{photo_num}'
                                
                                if photo_field in request.FILES:
                                    crop_data = request.POST.get(crop_data_field, '')
                                    image_file = process_cropped_image(crop_data, request.FILES[photo_field])
                                    PetPhoto.objects.create(
                                        pet=pet,
                                        image=image_file
                                    )
                
                # Handle ranked neighborhood preferences
                from .models import NeighborhoodPreference, Neighborhood
                
                # Clear existing neighborhood preferences
                NeighborhoodPreference.objects.filter(applicant=applicant).delete()
                
                # Get neighborhood rankings from form data
                neighborhood_rankings = []
                i = 1
                while request.POST.get(f'neighborhood_rank_{i}'):
                    neighborhood_id = request.POST.get(f'neighborhood_rank_{i}')
                    try:
                        neighborhood = Neighborhood.objects.get(id=neighborhood_id)
                        neighborhood_rankings.append((neighborhood, i))
                        i += 1
                    except Neighborhood.DoesNotExist:
                        continue
                
                # Create new ranked preferences
                for neighborhood, rank in neighborhood_rankings:
                    NeighborhoodPreference.objects.create(
                        applicant=applicant,
                        neighborhood=neighborhood,
                        preference_rank=rank
                    )
                
                # Handle building and apartment amenity preferences with priority levels
                from buildings.models import Amenity as BuildingAmenity
                from apartments.models import ApartmentAmenity
                from .models import ApplicantBuildingAmenityPreference, ApplicantApartmentAmenityPreference
                
                # Clear existing amenity preferences
                ApplicantBuildingAmenityPreference.objects.filter(applicant=applicant).delete()
                ApplicantApartmentAmenityPreference.objects.filter(applicant=applicant).delete()
                
                # Process building amenity preferences
                building_preferences_saved = 0
                for key, value in request.POST.items():
                    if key.startswith('building_amenity_') and value:
                        try:
                            # Validate slider value
                            slider_value = int(value)
                            if slider_value <= 0:
                                continue
                                
                            # Validate amenity ID
                            amenity_id_str = key.replace('building_amenity_', '')
                            amenity_id = int(amenity_id_str)
                            
                            # Map slider values to database values:
                            # Slider: 1 (Nice to Have) -> DB: 2
                            # Slider: 2 (Important) -> DB: 3  
                            # Slider: 3 (Must Have) -> DB: 4
                            value_mapping = {1: 2, 2: 3, 3: 4}
                            
                            if slider_value in value_mapping:
                                db_priority_level = value_mapping[slider_value]
                                amenity = BuildingAmenity.objects.get(id=amenity_id)
                                ApplicantBuildingAmenityPreference.objects.create(
                                    applicant=applicant,
                                    amenity=amenity,
                                    priority_level=db_priority_level
                                )
                                building_preferences_saved += 1
                        except (ValueError, BuildingAmenity.DoesNotExist):
                            # Log invalid data but continue processing other fields
                            print(f"Skipping invalid building amenity data: {key}={value}")
                            continue
                
                # Process apartment amenity preferences  
                apartment_preferences_saved = 0
                for key, value in request.POST.items():
                    if key.startswith('apartment_amenity_') and value:
                        try:
                            # Validate slider value
                            slider_value = int(value)
                            if slider_value <= 0:
                                continue
                                
                            # Validate amenity ID
                            amenity_id_str = key.replace('apartment_amenity_', '')
                            amenity_id = int(amenity_id_str)
                            
                            # Map slider values to database values
                            value_mapping = {1: 2, 2: 3, 3: 4}
                            
                            if slider_value in value_mapping:
                                db_priority_level = value_mapping[slider_value]
                                amenity = ApartmentAmenity.objects.get(id=amenity_id)
                                ApplicantApartmentAmenityPreference.objects.create(
                                    applicant=applicant,
                                    amenity=amenity,
                                    priority_level=db_priority_level
                                )
                                apartment_preferences_saved += 1
                        except (ValueError, ApartmentAmenity.DoesNotExist):
                            # Log invalid data but continue processing other fields
                            print(f"Skipping invalid apartment amenity data: {key}={value}")
                            continue
                
                # Log the saved preferences
                print(f"Saved {building_preferences_saved} building amenity preferences and {apartment_preferences_saved} apartment amenity preferences for {applicant.first_name}")
                
                messages.success(request, "Housing preferences saved! Let's finish with employment information.")
                return redirect('profile_step3')
    else:
        form = ApplicantHousingForm(instance=applicant)
    
    # Get completion status for progress bar
    completion_status = get_step_completion_status(applicant)
    
    # Calculate actual profile completion percentage
    completion_status = applicant.get_field_completion_status()
    completion_percentage = completion_status['overall_completion_percentage']
    
    # Get existing pets for the template
    from .models import Pet, NeighborhoodPreference
    existing_pets = Pet.objects.filter(applicant=applicant).prefetch_related('photos')
    
    # Get existing ranked neighborhood preferences
    existing_ranked_preferences = NeighborhoodPreference.objects.filter(
        applicant=applicant
    ).select_related('neighborhood').order_by('preference_rank')
    
    # Get all neighborhoods for the template
    from .models import Neighborhood
    all_neighborhoods = Neighborhood.objects.all().order_by('name')
    
    # Get building and apartment amenities for the template
    from buildings.models import Amenity as BuildingAmenity
    from apartments.models import ApartmentAmenity
    from .models import ApplicantBuildingAmenityPreference, ApplicantApartmentAmenityPreference
    
    all_building_amenities = BuildingAmenity.objects.all().order_by('name')
    all_apartment_amenities = ApartmentAmenity.objects.all().order_by('name')
    
    # Get existing amenity preferences for loading into sliders
    existing_building_preferences = ApplicantBuildingAmenityPreference.objects.filter(
        applicant=applicant
    ).select_related('amenity') if applicant else []
    
    existing_apartment_preferences = ApplicantApartmentAmenityPreference.objects.filter(
        applicant=applicant  
    ).select_related('amenity') if applicant else []
    
    context = {
        'form': form,
        'applicant': applicant,
        'existing_pets': existing_pets,
        'existing_ranked_preferences': existing_ranked_preferences,
        'all_neighborhoods': all_neighborhoods,
        'all_building_amenities': all_building_amenities,
        'all_apartment_amenities': all_apartment_amenities,
        'existing_building_preferences': existing_building_preferences,
        'existing_apartment_preferences': existing_apartment_preferences,
        'current_step': 2,
        'step_title': 'Step 2: Housing Needs and Preferences',
        'completion_status': completion_status,
        'completion_percentage': completion_percentage,
    }
    
    return render(request, 'applicants/profile_step2.html', context)


@login_required
def profile_step3(request):
    """
    Step 3: Income & Employment
    """
    # Get or create applicant profile
    try:
        applicant = request.user.applicant_profile
    except Applicant.DoesNotExist:
        applicant = Applicant.objects.create(
            user=request.user,
            email=request.user.email,
            first_name='',
            last_name='',
        )
    
    if request.method == 'POST':
        form = ApplicantEmploymentForm(request.POST, request.FILES, instance=applicant, request=request)
        if form.is_valid():
            with transaction.atomic():
                # Save the main form
                form.save()
                
                # Handle multiple jobs for all sections
                process_dynamic_jobs(request, applicant)
                
                # Handle multiple income sources for all sections
                process_dynamic_income_sources(request, applicant)
                
                # Handle multiple assets for all sections
                process_dynamic_assets(request, applicant)
            
            # Calculate completion after final save
            completion_status = applicant.get_field_completion_status()
            completion_percentage = completion_status['overall_completion_percentage']

            if completion_percentage == 100:
                messages.success(request, "Congratulations! Your profile is now complete.")
            else:
                messages.success(request, f"Profile updated! Your profile is now {completion_percentage}% complete.")
            
            return redirect('applicant_dashboard')
        else:
            messages.error(request, f"Please correct the errors below: {form.errors}")
    else:
        form = ApplicantEmploymentForm(instance=applicant)
    
    # Get completion status for progress bar
    completion_status = get_step_completion_status(applicant)
    
    # Calculate actual profile completion percentage
    completion_status = applicant.get_field_completion_status()
    completion_percentage = completion_status['overall_completion_percentage']
    
    context = {
        'form': form,
        'applicant': applicant,
        'current_step': 3,
        'step_title': 'Step 3: Income & Employment',
        'completion_status': completion_status,
        'completion_percentage': completion_percentage,
    }
    
    return render(request, 'applicants/profile_step3.html', context)


def process_dynamic_jobs(request, applicant):
    """Process multiple jobs from all sections (student, employed)"""
    # Clear existing jobs for this applicant to avoid duplicates
    applicant.jobs.all().delete()
    
    # Process student jobs
    for key, value in request.POST.items():
        if key.startswith('job_company_') and value.strip():
            index = key.split('_')[-1]
            
            # Get all related fields for this job
            company = request.POST.get(f'job_company_{index}', '').strip()
            position = request.POST.get(f'job_position_{index}', '').strip()
            income = request.POST.get(f'job_income_{index}', '')
            supervisor = request.POST.get(f'job_supervisor_{index}', '').strip()
            supervisor_email = request.POST.get(f'job_supervisor_email_{index}', '').strip()
            supervisor_phone = request.POST.get(f'job_supervisor_phone_{index}', '').strip()
            currently_employed = request.POST.get(f'job_current_{index}') == 'on'
            start_date = request.POST.get(f'job_start_{index}', '')
            end_date = request.POST.get(f'job_end_{index}', '')
            
            if company and position:  # Only create if we have essential data
                ApplicantJob.objects.create(
                    applicant=applicant,
                    company_name=company,
                    position=position,
                    annual_income=float(income) if income else None,
                    supervisor_name=supervisor,
                    supervisor_email=supervisor_email or None,
                    supervisor_phone=supervisor_phone,
                    currently_employed=currently_employed,
                    employment_start_date=start_date or None,
                    employment_end_date=end_date if not currently_employed and end_date else None,
                    job_type='student'
                )
    
    # Process employed jobs
    for key, value in request.POST.items():
        if key.startswith('employed_job_company_') and value.strip():
            index = key.split('_')[-1]
            
            # Get all related fields for this employed job
            company = request.POST.get(f'employed_job_company_{index}', '').strip()
            position = request.POST.get(f'employed_job_position_{index}', '').strip()
            income = request.POST.get(f'employed_job_income_{index}', '')
            supervisor = request.POST.get(f'employed_job_supervisor_{index}', '').strip()
            supervisor_email = request.POST.get(f'employed_job_supervisor_email_{index}', '').strip()
            supervisor_phone = request.POST.get(f'employed_job_supervisor_phone_{index}', '').strip()
            currently_employed = request.POST.get(f'employed_job_current_{index}') == 'on'
            start_date = request.POST.get(f'employed_job_start_{index}', '')
            end_date = request.POST.get(f'employed_job_end_{index}', '')
            
            if company and position:  # Only create if we have essential data
                ApplicantJob.objects.create(
                    applicant=applicant,
                    company_name=company,
                    position=position,
                    annual_income=float(income) if income else None,
                    supervisor_name=supervisor,
                    supervisor_email=supervisor_email or None,
                    supervisor_phone=supervisor_phone,
                    currently_employed=currently_employed,
                    employment_start_date=start_date or None,
                    employment_end_date=end_date if not currently_employed and end_date else None,
                    job_type='employed'
                )


def process_dynamic_income_sources(request, applicant):
    """Process multiple income sources from all sections"""
    # Clear existing income sources for this applicant
    applicant.income_sources.all().delete()
    
    # Process student income sources
    for key, value in request.POST.items():
        if key.startswith('income_source_') and value.strip():
            index = key.split('_')[-1]
            
            source = request.POST.get(f'income_source_{index}', '').strip()
            amount = request.POST.get(f'income_amount_{index}', '')
            
            if source and amount:
                ApplicantIncomeSource.objects.create(
                    applicant=applicant,
                    income_source=source,
                    average_annual_income=float(amount),
                    source_type='student'
                )
    
    # Process employed income sources
    for key, value in request.POST.items():
        if key.startswith('employed_income_source_') and value.strip():
            index = key.split('_')[-1]
            
            source = request.POST.get(f'employed_income_source_{index}', '').strip()
            amount = request.POST.get(f'employed_income_amount_{index}', '')
            
            if source and amount:
                ApplicantIncomeSource.objects.create(
                    applicant=applicant,
                    income_source=source,
                    average_annual_income=float(amount),
                    source_type='employed'
                )
    
    # Process other income sources
    for key, value in request.POST.items():
        if key.startswith('other_income_source_') and value.strip():
            index = key.split('_')[-1]
            
            source = request.POST.get(f'other_income_source_{index}', '').strip()
            amount = request.POST.get(f'other_income_amount_{index}', '')
            
            if source and amount:
                ApplicantIncomeSource.objects.create(
                    applicant=applicant,
                    income_source=source,
                    average_annual_income=float(amount),
                    source_type='other'
                )


def process_dynamic_assets(request, applicant):
    """Process multiple assets from all sections"""
    # Clear existing assets for this applicant
    applicant.assets.all().delete()
    
    # Process student assets
    for key, value in request.POST.items():
        if key.startswith('asset_name_') and value.strip():
            index = key.split('_')[-1]
            
            name = request.POST.get(f'asset_name_{index}', '').strip()
            balance = request.POST.get(f'asset_balance_{index}', '')
            
            if name and balance:
                ApplicantAsset.objects.create(
                    applicant=applicant,
                    asset_name=name,
                    account_balance=float(balance),
                    asset_type='student'
                )
    
    # Process employed assets
    for key, value in request.POST.items():
        if key.startswith('employed_asset_name_') and value.strip():
            index = key.split('_')[-1]
            
            name = request.POST.get(f'employed_asset_name_{index}', '').strip()
            balance = request.POST.get(f'employed_asset_balance_{index}', '')
            
            if name and balance:
                ApplicantAsset.objects.create(
                    applicant=applicant,
                    asset_name=name,
                    account_balance=float(balance),
                    asset_type='employed'
                )
    
    # Process other assets
    for key, value in request.POST.items():
        if key.startswith('other_asset_name_') and value.strip():
            index = key.split('_')[-1]
            
            name = request.POST.get(f'other_asset_name_{index}', '').strip()
            balance = request.POST.get(f'other_asset_balance_{index}', '')
            
            if name and balance:
                ApplicantAsset.objects.create(
                    applicant=applicant,
                    asset_name=name,
                    account_balance=float(balance),
                    asset_type='other'
                )
