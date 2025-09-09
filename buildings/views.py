from django.shortcuts import render, redirect, get_object_or_404
from .forms import BuildingForm, BuildingImageForm, BuildingAccessForm, BuildingSpecialForm
from .models import Building
from .decorators import admin_only, authenticated_required
from django.contrib import messages
from django.db.models import Count, Q
from django.core.exceptions import ValidationError
from django.db import transaction
import logging

# Set up logging for error tracking
logger = logging.getLogger(__name__)


@authenticated_required
def buildings_list(request):
    """
    Display list of all buildings with apartment counts and dashboard statistics.
    Read-only access for all authenticated users.
    """
    try:
        buildings = Building.objects.annotate(
            active_apartments_count=Count('apartments', filter=Q(apartments__status='available'))
        ).prefetch_related('images', 'apartments').order_by('name')
        
        # Calculate dashboard statistics
        total_apartments = sum(building.active_apartments_count for building in buildings)
        buildings_with_photos = sum(1 for building in buildings if building.images.exists())
        unique_cities = len(set(building.city for building in buildings))
        
        context = {
            'buildings': buildings,
            'total_apartments': total_apartments,
            'buildings_with_photos': buildings_with_photos,
            'unique_cities': unique_cities,
        }
        
        return render(request, 'buildings/buildings_list.html', context)
        
    except Exception as e:
        logger.error(f"Error loading buildings list: {str(e)}")
        messages.error(request, "An error occurred while loading the buildings list. Please try again.")
        return render(request, 'buildings/buildings_list.html', {'buildings': []})


@admin_only
def create_building(request):
    """
    Create a new building with images, access points, and specials.
    Admin access only.
    """
    building = None
    building_form = BuildingForm(request.POST or None)
    image_form = BuildingImageForm(request.POST or None, request.FILES or None)
    access_form = BuildingAccessForm(request.POST or None, request.FILES or None)
    special_form = BuildingSpecialForm(request.POST or None)

    try:
        # Phase 1: Creating the Building
        if 'building_submit' in request.POST:
            if building_form.is_valid():
                with transaction.atomic():
                    building = building_form.save()
                    logger.info(f"Building '{building.name}' created by user {request.user.email}")
                    messages.success(request, 
                        f'Building "{building.name}" created successfully! '
                        'Now let\'s add some images.'
                    )
                    # Redirect to Step 2: Images
                    return redirect('building_step2', building_id=building.id)
            else:
                messages.error(request, "Please correct the errors below and try again.")
                building = None

        # Phase 2: Attach Images, Access, Specials (if building exists)
        if request.method == 'POST' and 'building_id' in request.POST:
            try:
                building = get_object_or_404(Building, id=request.POST.get('building_id'))
            except Building.DoesNotExist:
                messages.error(request, "Building not found. Please try again.")
                return redirect('buildings_list')

            if 'image_submit' in request.POST:
                if image_form.is_valid():
                    try:
                        with transaction.atomic():
                            image = image_form.save(commit=False)
                            image.building = building
                            image.save()
                            messages.success(request, 'Image uploaded successfully.')
                    except Exception as e:
                        logger.error(f"Error uploading image for building {building.id}: {str(e)}")
                        messages.error(request, "Failed to upload image. Please try again.")
                else:
                    messages.error(request, "Invalid image file. Please select a valid image.")

            if 'access_submit' in request.POST:
                if access_form.is_valid():
                    try:
                        with transaction.atomic():
                            access = access_form.save(commit=False)
                            access.building = building
                            access.save()
                            messages.success(request, 'Access point added successfully.')
                    except Exception as e:
                        logger.error(f"Error adding access point for building {building.id}: {str(e)}")
                        messages.error(request, "Failed to add access point. Please try again.")
                else:
                    messages.error(request, "Please correct the access point information and try again.")

            if 'special_submit' in request.POST:
                if special_form.is_valid():
                    try:
                        with transaction.atomic():
                            special = special_form.save(commit=False)
                            special.building = building
                            special.save()
                            messages.success(request, 'Special added successfully.')
                    except Exception as e:
                        logger.error(f"Error adding special for building {building.id}: {str(e)}")
                        messages.error(request, "Failed to add special. Please try again.")
                else:
                    messages.error(request, "Please correct the special information and try again.")

    except Exception as e:
        logger.error(f"Unexpected error in create_building: {str(e)}")
        messages.error(request, "An unexpected error occurred. Please try again.")
        return redirect('buildings_list')

    return render(request, 'buildings/create_building.html', {
        'building_form': building_form,
        'image_form': image_form,
        'access_form': access_form,
        'special_form': special_form,
        'building': building,
    })


@admin_only
def building_step2(request, building_id):
    """Step 2: Building Images"""
    try:
        building = get_object_or_404(Building, id=building_id)
    except Building.DoesNotExist:
        messages.error(request, "Building not found.")
        return redirect('buildings_list')

    image_form = BuildingImageForm(request.POST or None, request.FILES or None, building_id=building_id)

    if request.method == 'POST':
        if 'image_submit' in request.POST:
            if image_form.is_valid():
                try:
                    with transaction.atomic():
                        image = image_form.save(commit=False)
                        image.building = building
                        image.save()
                        messages.success(request, 'Image uploaded successfully.')
                        # Stay on same page to allow multiple uploads
                        return redirect('building_step2', building_id=building.id)
                except Exception as e:
                    logger.error(f"Error uploading image for building {building.id}: {str(e)}")
                    messages.error(request, "Failed to upload image. Please try again.")
            else:
                messages.error(request, "Invalid image file. Please select a valid image.")
        
        elif 'skip_images' in request.POST:
            messages.info(request, "Skipped image upload. You can add images later.")
            return redirect('building_step3', building_id=building.id)
        
        elif 'next_step' in request.POST:
            return redirect('building_step3', building_id=building.id)

    context = {
        'building': building,
        'image_form': image_form,
        'current_step': 2,
        'step_title': 'Step 2: Building Images'
    }
    
    return render(request, 'buildings/building_step2.html', context)


@admin_only
def building_step3(request, building_id):
    """Step 3: Access Information"""
    try:
        building = get_object_or_404(Building, id=building_id)
    except Building.DoesNotExist:
        messages.error(request, "Building not found.")
        return redirect('buildings_list')

    access_form = BuildingAccessForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if 'access_submit' in request.POST:
            if access_form.is_valid():
                try:
                    with transaction.atomic():
                        access = access_form.save(commit=False)
                        access.building = building
                        access.save()
                        messages.success(request, 'Access information added successfully.')
                        return redirect('building_step3', building_id=building.id)
                except Exception as e:
                    logger.error(f"Error adding access info for building {building.id}: {str(e)}")
                    messages.error(request, "Failed to add access information. Please try again.")
            else:
                messages.error(request, "Please correct the errors and try again.")
        
        elif 'skip_access' in request.POST:
            messages.info(request, "Skipped access information. You can add this later.")
            return redirect('building_step4', building_id=building.id)
        
        elif 'next_step' in request.POST:
            return redirect('building_step4', building_id=building.id)

    context = {
        'building': building,
        'access_form': access_form,
        'current_step': 3,
        'step_title': 'Step 3: Access Information'
    }
    
    return render(request, 'buildings/building_step3.html', context)


@admin_only
def building_step4(request, building_id):
    """Step 4: Special Offers & Promotions"""
    try:
        building = get_object_or_404(Building, id=building_id)
    except Building.DoesNotExist:
        messages.error(request, "Building not found.")
        return redirect('buildings_list')

    special_form = BuildingSpecialForm(request.POST or None)

    if request.method == 'POST':
        if 'special_submit' in request.POST:
            if special_form.is_valid():
                try:
                    with transaction.atomic():
                        special = special_form.save(commit=False)
                        special.building = building
                        special.save()
                        messages.success(request, 'Special offer added successfully.')
                        return redirect('building_step4', building_id=building.id)
                except Exception as e:
                    logger.error(f"Error adding special offer for building {building.id}: {str(e)}")
                    messages.error(request, "Failed to add special offer. Please try again.")
            else:
                messages.error(request, "Please correct the errors and try again.")
        
        elif 'skip_specials' in request.POST:
            messages.info(request, "Skipped special offers. You can add these later.")
            return redirect('building_complete', building_id=building.id)
        
        elif 'complete_building' in request.POST:
            return redirect('building_complete', building_id=building.id)

    context = {
        'building': building,
        'special_form': special_form,
        'current_step': 4,
        'step_title': 'Step 4: Promotions & Special Offers'
    }
    
    return render(request, 'buildings/building_step4.html', context)


@admin_only
def building_complete(request, building_id):
    """Building Creation Complete"""
    try:
        building = get_object_or_404(Building, id=building_id)
    except Building.DoesNotExist:
        messages.error(request, "Building not found.")
        return redirect('buildings_list')

    context = {
        'building': building,
        'current_step': 5,
        'step_title': 'Building Setup Complete!'
    }
    
    return render(request, 'buildings/building_complete.html', context)



@admin_only
def building_detail(request, building_id):
    """
    Edit building details, manage images, access points, and specials.
    Admin access only.
    """
    try:
        building = get_object_or_404(Building, id=building_id)
    except Building.DoesNotExist:
        messages.error(request, "Building not found.")
        return redirect('buildings_list')

    building_form = BuildingForm(instance=building)
    image_form = BuildingImageForm(building_id=building_id)
    access_form = BuildingAccessForm()
    special_form = BuildingSpecialForm()

    if request.method == 'POST':
        try:
            if 'building_submit' in request.POST:
                building_form = BuildingForm(request.POST, instance=building)
                if building_form.is_valid():
                    with transaction.atomic():
                        building_form.save()
                        logger.info(f"Building '{building.name}' updated by user {request.user.email}")
                        messages.success(request, 'Building information updated successfully.')
                        return redirect('building_detail', building_id=building.id)
                else:
                    messages.error(request, "Please correct the errors below and try again.")

            elif 'image_submit' in request.POST:
                image_form = BuildingImageForm(request.POST, request.FILES)
                if image_form.is_valid():
                    try:
                        with transaction.atomic():
                            image = image_form.save(commit=False)
                            image.building = building
                            image.save()
                            messages.success(request, 'Image uploaded successfully.')
                            return redirect('building_detail', building_id=building.id)
                    except Exception as e:
                        logger.error(f"Error uploading image for building {building.id}: {str(e)}")
                        messages.error(request, "Failed to upload image. Please try again.")
                else:
                    messages.error(request, "Invalid image file. Please select a valid image.")

            elif 'access_submit' in request.POST:
                access_form = BuildingAccessForm(request.POST, request.FILES)
                if access_form.is_valid():
                    try:
                        with transaction.atomic():
                            access = access_form.save(commit=False)
                            access.building = building
                            access.save()
                            messages.success(request, 'Access point added successfully.')
                            return redirect('building_detail', building_id=building.id)
                    except Exception as e:
                        logger.error(f"Error adding access point for building {building.id}: {str(e)}")
                        messages.error(request, "Failed to add access point. Please try again.")
                else:
                    messages.error(request, "Please correct the access point information and try again.")

            elif 'special_submit' in request.POST:
                special_form = BuildingSpecialForm(request.POST)
                if special_form.is_valid():
                    try:
                        with transaction.atomic():
                            special = special_form.save(commit=False)
                            special.building = building
                            special.save()
                            messages.success(request, 'Special added successfully.')
                            return redirect('building_detail', building_id=building.id)
                    except Exception as e:
                        logger.error(f"Error adding special for building {building.id}: {str(e)}")
                        messages.error(request, "Failed to add special. Please try again.")
                else:
                    messages.error(request, "Please correct the special information and try again.")

        except Exception as e:
            logger.error(f"Unexpected error in building_detail for building {building_id}: {str(e)}")
            messages.error(request, "An unexpected error occurred. Please try again.")

    return render(request, 'buildings/building_detail.html', {
        'building': building,
        'building_form': building_form,
        'image_form': image_form,
        'access_form': access_form,
        'special_form': special_form,
    })

@authenticated_required
def building_overview(request, building_id):
    """
    Display building overview with details, amenities, and apartments.
    Read-only access for all authenticated users.
    """
    try:
        building = get_object_or_404(Building, id=building_id)
        
        # Get additional building statistics
        apartments = building.apartments.all()
        total_count = apartments.count()
        available_count = apartments.filter(status='available').count()
        occupied_count = apartments.filter(status='occupied').count()
        
        # Calculate occupancy rate
        occupancy_rate = round((occupied_count / total_count * 100)) if total_count > 0 else 0
        
        # Calculate average rent
        from django.db.models import Avg
        avg_rent_result = apartments.aggregate(avg_rent=Avg('rent_price'))
        avg_rent = avg_rent_result['avg_rent'] if avg_rent_result['avg_rent'] else 0
        
        context = {
            'building': building,
            'apartments': apartments,
            'total_apartments': total_count,
            'available_apartments': available_count,
            'occupancy_rate': occupancy_rate,
            'avg_rent': avg_rent,
        }
        
        return render(request, 'buildings/building_overview.html', context)
        
    except Building.DoesNotExist:
        messages.error(request, "Building not found.")
        return redirect('buildings_list')
    except Exception as e:
        logger.error(f"Error loading building overview for building {building_id}: {str(e)}")
        messages.error(request, "An error occurred while loading the building overview. Please try again.")
        return redirect('buildings_list')
