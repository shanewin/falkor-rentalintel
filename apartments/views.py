from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from .models import Apartment, ApartmentImage
from buildings.models import Building
from .forms import ApartmentForm, ApartmentImageForm, ApartmentBasicForm, ApartmentAmenitiesForm, ApartmentDetailsForm
from django.http import JsonResponse



def apartments_list(request):
    apartments = Apartment.objects.all().select_related('building').prefetch_related('images')
    return render(request, 'apartments/apartments_list.html', {'apartments': apartments})



def create_apartment(request, building_id=None):
    """Redirect to the new multi-step apartment creation workflow"""
    if building_id:
        return redirect('create_apartment_v2_with_building', building_id=building_id)
    else:
        return redirect('create_apartment_v2')




def apartment_detail(request, apartment_id=None, building_id=None):
    apartment = None
    building = None

    if apartment_id:
        apartment = get_object_or_404(Apartment, id=apartment_id)
        building = apartment.building
    elif building_id:
        building = get_object_or_404(Building, id=building_id)

    if request.method == 'POST':
        if 'apartment_submit' in request.POST:
            apartment_form = ApartmentForm(request.POST, instance=apartment)
            if apartment_form.is_valid():
                apartment = apartment_form.save()
                messages.success(request, 'Apartment details saved successfully.')
                return redirect('apartment_detail', apartment_id=apartment.id)

        elif 'image_submit' in request.POST and apartment:
            image_form = ApartmentImageForm(request.POST, request.FILES)
            if image_form.is_valid():
                image = image_form.save(commit=False)
                image.apartment = apartment
                image.save()
                messages.success(request, 'Image uploaded successfully.')
                return redirect('apartment_detail', apartment_id=apartment.id)

    else:
        apartment_form = ApartmentForm(instance=apartment, initial={'building': building})
        image_form = ApartmentImageForm()

    return render(request, 'apartments/apartment_detail.html', {
        'apartment': apartment,
        'apartment_form': apartment_form,
        'image_form': image_form,
        'building': building,
    })


def apartment_overview(request, apartment_id):
    apartment = get_object_or_404(Apartment, id=apartment_id)
    
    # Track apartment view activity for applicants
    if request.user.is_authenticated and hasattr(request.user, 'applicant_profile'):
        try:
            from applicants.activity_tracker import ActivityTracker
            ActivityTracker.track_apartment_view(
                applicant=request.user.applicant_profile,
                apartment=apartment,
                request=request
            )
        except Exception as e:
            # Log error but don't break the page
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to track apartment view: {e}")
    
    return render(request, 'apartments/apartment_overview.html', {'apartment': apartment})



def get_apartment_data(request, apartment_id):
    try:
        apartment = Apartment.objects.get(id=apartment_id)
        data = {
            "rent_price": str(apartment.rent_price),
            "bedrooms": str(apartment.bedrooms),
            "bathrooms": str(apartment.bathrooms),
        }
        return JsonResponse(data)
    except Apartment.DoesNotExist:
        return JsonResponse({"error": "Apartment not found"}, status=404)


# Multi-step apartment creation views
def create_apartment_v2(request, building_id=None):
    """Step 1: Basic Apartment Information"""
    building = None
    if building_id:
        building = get_object_or_404(Building, id=building_id)

    basic_form = ApartmentBasicForm(request.POST or None, initial={'building': building})

    if request.method == 'POST' and 'apartment_submit' in request.POST:
        if basic_form.is_valid():
            apartment = basic_form.save()
            messages.success(request, f'Apartment {apartment.unit_number} created successfully! Now let\'s add images.')
            return redirect('apartment_step2', apartment_id=apartment.id)
        else:
            messages.error(request, "Please correct the errors below and try again.")

    context = {
        'basic_form': basic_form,
        'building': building,
        'current_step': 1,
        'step_title': 'Step 1: Basic Information'
    }
    
    return render(request, 'apartments/apartment_step1.html', context)


def apartment_step2(request, apartment_id):
    """Step 2: Images Upload"""
    try:
        apartment = get_object_or_404(Apartment, id=apartment_id)
    except Apartment.DoesNotExist:
        messages.error(request, "Apartment not found.")
        return redirect('apartments_list')

    image_form = ApartmentImageForm(request.POST or None, request.FILES or None)

    if request.method == 'POST':
        if 'image_submit' in request.POST:
            if image_form.is_valid():
                try:
                    image = image_form.save(commit=False)
                    image.apartment = apartment
                    image.save()
                    messages.success(request, 'Image uploaded successfully.')
                    return redirect('apartment_step2', apartment_id=apartment.id)
                except Exception as e:
                    messages.error(request, "Failed to upload image. Please try again.")
            else:
                messages.error(request, "Invalid image file. Please select a valid image.")
        
        elif 'skip_images' in request.POST:
            messages.info(request, "Skipped image upload. You can add images later.")
            return redirect('apartment_step3', apartment_id=apartment.id)
        
        elif 'next_step' in request.POST:
            return redirect('apartment_step3', apartment_id=apartment.id)

    context = {
        'apartment': apartment,
        'image_form': image_form,
        'current_step': 2,
        'step_title': 'Step 2: Images'
    }
    
    return render(request, 'apartments/apartment_step2.html', context)


def apartment_step3(request, apartment_id):
    """Step 3: Amenities and Features"""
    try:
        apartment = get_object_or_404(Apartment, id=apartment_id)
    except Apartment.DoesNotExist:
        messages.error(request, "Apartment not found.")
        return redirect('apartments_list')

    amenities_form = ApartmentAmenitiesForm(request.POST or None, instance=apartment)

    if request.method == 'POST':
        if 'amenities_submit' in request.POST:
            if amenities_form.is_valid():
                try:
                    amenities_form.save()
                    messages.success(request, 'Amenities and features saved successfully.')
                    return redirect('apartment_step4', apartment_id=apartment.id)
                except Exception as e:
                    messages.error(request, "Failed to save amenities. Please try again.")
            else:
                messages.error(request, "Please correct the errors and try again.")
        
        elif 'skip_amenities' in request.POST:
            messages.info(request, "Skipped amenities. You can add these later.")
            return redirect('apartment_step4', apartment_id=apartment.id)

    context = {
        'apartment': apartment,
        'amenities_form': amenities_form,
        'current_step': 3,
        'step_title': 'Step 3: Amenities & Features'
    }
    
    return render(request, 'apartments/apartment_step3.html', context)


def apartment_step4(request, apartment_id):
    """Step 4: Additional Details & Completion"""
    try:
        apartment = get_object_or_404(Apartment, id=apartment_id)
    except Apartment.DoesNotExist:
        messages.error(request, "Apartment not found.")
        return redirect('apartments_list')

    details_form = ApartmentDetailsForm(request.POST or None, instance=apartment)

    if request.method == 'POST':
        if 'details_submit' in request.POST:
            if details_form.is_valid():
                try:
                    details_form.save()
                    messages.success(request, 'Additional details saved successfully.')
                    return redirect('apartment_complete', apartment_id=apartment.id)
                except Exception as e:
                    messages.error(request, "Failed to save details. Please try again.")
            else:
                messages.error(request, "Please correct the errors and try again.")
        
        elif 'skip_details' in request.POST:
            messages.info(request, "Skipped additional details. You can add these later.")
            return redirect('apartment_complete', apartment_id=apartment.id)

    context = {
        'apartment': apartment,
        'details_form': details_form,
        'current_step': 4,
        'step_title': 'Step 4: Additional Details'
    }
    
    return render(request, 'apartments/apartment_step4.html', context)


def apartment_complete(request, apartment_id):
    """Apartment Creation Complete"""
    try:
        apartment = get_object_or_404(Apartment, id=apartment_id)
    except Apartment.DoesNotExist:
        messages.error(request, "Apartment not found.")
        return redirect('apartments_list')

    context = {
        'apartment': apartment,
        'current_step': 5,
        'step_title': 'Apartment Setup Complete!'
    }
    
    return render(request, 'apartments/apartment_complete.html', context)
