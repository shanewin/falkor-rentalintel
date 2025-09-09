from django import forms
from .models import Applicant, ApplicantPhoto, Pet, PetPhoto, Amenity, Neighborhood, InteractionLog
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Row, Column, Field, Div, Submit, HTML
from crispy_forms.bootstrap import InlineCheckboxes
from cloudinary.forms import CloudinaryFileField

# Multi-step forms for progressive profile completion

class ApplicantBasicInfoForm(forms.ModelForm):
    """Step 1: Basic Information Form"""
    
    class Meta:
        model = Applicant
        fields = [
            'first_name', 'last_name', 'phone_number', 'email',
            'street_address_1', 'street_address_2', 'city', 'state', 'zip_code',
            'housing_status', 'current_landlord_name', 'current_landlord_phone', 'current_landlord_email',
            'date_of_birth',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'state': forms.Select(attrs={
                'class': 'form-select select2',
                'data-placeholder': 'Select State'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Only first_name, last_name, and email are required
        required_fields = ['first_name', 'last_name', 'email']
        for field_name, field in self.fields.items():
            if field_name not in required_fields:
                field.required = False
            
            # Remove label suffixes
            field.label_suffix = ''
            if field.required:
                field.widget.attrs['required'] = 'required'

        # Crispy Forms setup
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'doorway-form'

        self.helper.layout = Layout(
            # Profile Photo Section
            HTML('''
            <div class="mb-4 profile-photo-section">
                <label class="form-label">Profile Photo</label>
                <div class="row align-items-center">
                    <div class="col-auto">
                        <div class="profile-photo-container position-relative">
                            {% if form.instance.photos.all %}
                                <img src="{{ form.instance.photos.first.thumbnail_url }}" 
                                     alt="Profile Photo" 
                                     class="preview-image rounded-circle border border-2 border-warning" 
                                     width="120" 
                                     height="120" 
                                     style="object-fit: cover;">
                            {% else %}
                                <div class="image-placeholder bg-light rounded-circle border border-2 border-secondary d-flex align-items-center justify-content-center" 
                                     style="width: 120px; height: 120px;">
                                    <i class="fas fa-user fa-3x text-muted"></i>
                                </div>
                            {% endif %}
                        </div>
                    </div>
                    <div class="col">
                        <h6 class="mb-2">Upload Your Profile Photo</h6>
                        <p class="text-muted small mb-3">Choose a professional photo that represents you well. Accepted formats: JPG, PNG, GIF (max 10MB)</p>
                        
                        <div class="d-flex gap-2 mb-3 image-cropper-buttons">
                            <button type="button" 
                                    class="btn btn-primary btn-sm"
                                    onclick="document.getElementById('id_profile_photo').click()">
                                <i class="fas fa-camera"></i> Upload Photo
                            </button>
                        </div>
                        
                        <input type="file" 
                               name="profile_photo" 
                               id="id_profile_photo" 
                               accept="image/*"
                               style="display: none;"
                               class="form-control">
                               
                        <!-- Crop transformation data -->
                        <input type="hidden" id="crop-data" name="crop_data" value="">
                    </div>
                </div>
            </div>
            '''),
            
            Fieldset(
                'Personal Information',
                Row(
                    Column(Field('first_name', placeholder="First Name"), css_class='col-md-6'),
                    Column(Field('last_name', placeholder="Last Name"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('phone_number', placeholder="(555) 555-5555"), css_class='col-md-6'),
                    Column('email', css_class='col-md-6'),
                ),
            ),
            
            Fieldset(
                'Current Address',
                Row(
                    Column('street_address_1', css_class='col-md-8'),
                    Column('street_address_2', css_class='col-md-4'),
                ),
                Row(
                    Column('city', css_class='col-md-5'),
                    Column('state', css_class='col-md-3'),
                    Column('zip_code', css_class='col-md-4'),
                ),
                HTML('''
                <div class="form-check mb-3">
                    <input class="form-check-input" type="checkbox" id="is_rental_checkbox" name="is_rental_checkbox">
                    <label class="form-check-label" for="is_rental_checkbox">
                        Is this a Rental?
                    </label>
                </div>
                '''),
                Field('housing_status', type="hidden"),
                Div(
                    Row(
                        Column(Field('current_landlord_name', placeholder="Landlord's Name"), css_class='col-md-4'),
                        Column(Field('current_landlord_phone', placeholder="(555) 555-5555"), css_class='col-md-4'),
                        Column(Field('current_landlord_email', placeholder="Landlord's Email"), css_class='col-md-4'),
                    ),
                    css_id='landlord_fields',
                    css_class='d-none mb-2'
                ),
                HTML('''
                <div class="mt-2">
                    <button type="button" id="add-previous-address-btn" class="btn btn-sm" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Previous Address
                    </button>
                </div>
                <div id="previous-addresses-container">
                    <!-- Dynamic previous address forms will be added here -->
                </div>
                '''),
            ),
            
            Fieldset(
                'Identification',
                Row(
                    Column('date_of_birth', css_class='col-md-6'),
                    Column(css_class='col-md-6'),
                ),
                HTML('''
                <div class="mt-3">
                    <label class="form-label">
                        Select Identification Type(s)
                        <i class="fas fa-question-circle text-muted ms-2" 
                           data-bs-toggle="tooltip" 
                           data-bs-placement="right" 
                           title="At least one form of identification with photos is required for your application. Uploading multiple types (such as Driver's License AND Passport) will help us process your application faster and improve your chances of approval.">
                        </i>
                    </label>
                    <div class="id-type-checkboxes">
                        <div class="form-check mb-3">
                            <input class="form-check-input id-type-checkbox" type="checkbox" value="passport" id="id_passport" style="width: 1.25em; height: 1.25em;">
                            <label class="form-check-label fs-5 ms-2" for="id_passport" style="padding-top: 2px;">
                                <i class="fas fa-passport"></i> Passport
                            </label>
                        </div>
                        <div class="form-check mb-3">
                            <input class="form-check-input id-type-checkbox" type="checkbox" value="driver_license" id="id_driver_license" style="width: 1.25em; height: 1.25em;">
                            <label class="form-check-label fs-5 ms-2" for="id_driver_license" style="padding-top: 2px;">
                                <i class="fas fa-id-card"></i> Driver's License
                            </label>
                        </div>
                        <div class="form-check mb-3">
                            <input class="form-check-input id-type-checkbox" type="checkbox" value="state_id" id="id_state_id" style="width: 1.25em; height: 1.25em;">
                            <label class="form-check-label fs-5 ms-2" for="id_state_id" style="padding-top: 2px;">
                                <i class="fas fa-id-badge"></i> State ID
                            </label>
                        </div>
                    </div>
                    
                    <!-- Upload sections that will be shown/hidden based on selection -->
                    <div id="passport_upload" class="id-upload-section mt-3" style="display: none;">
                        <div class="card">
                            <div class="card-body">
                                <h6 class="mb-3"><i class="fas fa-passport"></i> Upload Passport</h6>
                                <div class="row align-items-center">
                                    <div class="col-auto">
                                        <div class="passport-container position-relative">
                                            <div class="image-placeholder bg-light rounded border border-2 border-secondary d-flex align-items-center justify-content-center" 
                                                 style="width: 200px; height: 125px;">
                                                <i class="fas fa-passport fa-3x text-muted"></i>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="col">
                                        <p class="text-muted small mb-3">Upload a clear photo of your passport</p>
                                        <div class="d-flex gap-2 mb-3 image-cropper-buttons">
                                            <button type="button" class="btn btn-primary btn-sm"
                                                    onclick="document.getElementById('id_passport_document').click()">
                                                <i class="fas fa-camera"></i> Upload Passport
                                            </button>
                                        </div>
                                        <input type="file" name="passport_document" id="id_passport_document" 
                                               accept="image/*" style="display: none;" class="form-control">
                                        <input type="hidden" id="crop-data-passport" name="crop_data_passport" value="">
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div id="driver_license_upload" class="id-upload-section mt-3" style="display: none;">
                        <div class="card">
                            <div class="card-body">
                                <h6 class="mb-3"><i class="fas fa-id-card"></i> Upload Driver's License</h6>
                                
                                <!-- Front of Driver's License -->
                                <div class="mb-4">
                                    <label class="form-label fw-bold">Front of Driver's License</label>
                                    <div class="row align-items-center">
                                        <div class="col-auto">
                                            <div class="driver-license-front-container position-relative">
                                                <div class="image-placeholder bg-light rounded border border-2 border-secondary d-flex align-items-center justify-content-center" 
                                                     style="width: 200px; height: 125px;">
                                                    <i class="fas fa-id-card fa-3x text-muted"></i>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col">
                                            <p class="text-muted small mb-3">Upload a clear photo of the front of your driver's license</p>
                                            <div class="d-flex gap-2 mb-3 image-cropper-buttons">
                                                <button type="button" class="btn btn-primary btn-sm"
                                                        onclick="document.getElementById('id_driver_license_front').click()">
                                                    <i class="fas fa-camera"></i> Upload Front
                                                </button>
                                            </div>
                                            <input type="file" name="driver_license_front" id="id_driver_license_front" 
                                                   accept="image/*" style="display: none;" class="form-control">
                                            <input type="hidden" id="crop-data-driver-front" name="crop_data_driver_front" value="">
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Back of Driver's License -->
                                <div class="mb-3">
                                    <label class="form-label fw-bold">Back of Driver's License</label>
                                    <div class="row align-items-center">
                                        <div class="col-auto">
                                            <div class="driver-license-back-container position-relative">
                                                <div class="image-placeholder bg-light rounded border border-2 border-secondary d-flex align-items-center justify-content-center" 
                                                     style="width: 200px; height: 125px;">
                                                    <i class="fas fa-id-card fa-3x text-muted"></i>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col">
                                            <p class="text-muted small mb-3">Upload a clear photo of the back of your driver's license</p>
                                            <div class="d-flex gap-2 mb-3 image-cropper-buttons">
                                                <button type="button" class="btn btn-primary btn-sm"
                                                        onclick="document.getElementById('id_driver_license_back').click()">
                                                    <i class="fas fa-camera"></i> Upload Back
                                                </button>
                                            </div>
                                            <input type="file" name="driver_license_back" id="id_driver_license_back" 
                                                   accept="image/*" style="display: none;" class="form-control">
                                            <input type="hidden" id="crop-data-driver-back" name="crop_data_driver_back" value="">
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div id="state_id_upload" class="id-upload-section mt-3" style="display: none;">
                        <div class="card">
                            <div class="card-body">
                                <h6 class="mb-3"><i class="fas fa-id-badge"></i> Upload State ID</h6>
                                
                                <!-- Front of State ID -->
                                <div class="mb-4">
                                    <label class="form-label fw-bold">Front of State ID</label>
                                    <div class="row align-items-center">
                                        <div class="col-auto">
                                            <div class="state-id-front-container position-relative">
                                                <div class="image-placeholder bg-light rounded border border-2 border-secondary d-flex align-items-center justify-content-center" 
                                                     style="width: 200px; height: 125px;">
                                                    <i class="fas fa-id-badge fa-3x text-muted"></i>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col">
                                            <p class="text-muted small mb-3">Upload a clear photo of the front of your state ID</p>
                                            <div class="d-flex gap-2 mb-3 image-cropper-buttons">
                                                <button type="button" class="btn btn-primary btn-sm"
                                                        onclick="document.getElementById('id_state_id_front').click()">
                                                    <i class="fas fa-camera"></i> Upload Front
                                                </button>
                                            </div>
                                            <input type="file" name="state_id_front" id="id_state_id_front" 
                                                   accept="image/*" style="display: none;" class="form-control">
                                            <input type="hidden" id="crop-data-state-front" name="crop_data_state_front" value="">
                                        </div>
                                    </div>
                                </div>
                                
                                <!-- Back of State ID -->
                                <div class="mb-3">
                                    <label class="form-label fw-bold">Back of State ID</label>
                                    <div class="row align-items-center">
                                        <div class="col-auto">
                                            <div class="state-id-back-container position-relative">
                                                <div class="image-placeholder bg-light rounded border border-2 border-secondary d-flex align-items-center justify-content-center" 
                                                     style="width: 200px; height: 125px;">
                                                    <i class="fas fa-id-badge fa-3x text-muted"></i>
                                                </div>
                                            </div>
                                        </div>
                                        <div class="col">
                                            <p class="text-muted small mb-3">Upload a clear photo of the back of your state ID</p>
                                            <div class="d-flex gap-2 mb-3 image-cropper-buttons">
                                                <button type="button" class="btn btn-primary btn-sm"
                                                        onclick="document.getElementById('id_state_id_back').click()">
                                                    <i class="fas fa-camera"></i> Upload Back
                                                </button>
                                            </div>
                                            <input type="file" name="state_id_back" id="id_state_id_back" 
                                                   accept="image/*" style="display: none;" class="form-control">
                                            <input type="hidden" id="crop-data-state-back" name="crop_data_state_back" value="">
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                '''),
            ),
            
            
            # Navigation Buttons
            Div(
                Submit('basic_info_submit', 'Save & Continue', css_class='btn btn-doorway-primary btn-lg me-3'),
                HTML('<a href="{% url \'profile_step2\' %}" class="btn btn-outline-secondary btn-lg">Skip</a>'),
                css_class='text-center mt-4'
            )
        )


class ApplicantHousingForm(forms.ModelForm):
    """Step 2: Housing Needs and Preferences Form"""
    
    BEDROOM_CHOICES = [
        ('', 'Any'),
        ('studio', 'Studio (0)'),
        ('1', '1'),
        ('2', '2'),
        ('3', '3'),
        ('4', '4'),
        ('5+', '5+'),
    ]
    
    BATHROOM_CHOICES = [
        ('', 'Any'),
        ('1', '1'),
        ('1.5', '1.5'),
        ('2', '2'),
        ('2.5', '2.5'),
        ('3', '3'),
        ('3.5', '3.5'),
        ('4', '4'),
        ('5+', '5+'),
    ]
    
    class Meta:
        model = Applicant
        fields = [
            'desired_move_in_date', 'min_bedrooms', 'max_bedrooms', 'min_bathrooms', 'max_bathrooms',
            'max_rent_budget', 'open_to_roommates',
            'amenities',
        ]
        widgets = {
            'desired_move_in_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'max_rent_budget': forms.NumberInput(attrs={
                'class': 'form-control currency-field',
                'step': '0.01',
                'placeholder': '2500.00',
                'min': '0'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set up bedroom range dropdowns
        self.fields['min_bedrooms'] = forms.ChoiceField(
            choices=self.BEDROOM_CHOICES,
            required=False,
            label='Minimum Bedrooms',
            widget=forms.Select(attrs={'class': 'form-select select2'})
        )
        self.fields['max_bedrooms'] = forms.ChoiceField(
            choices=self.BEDROOM_CHOICES,
            required=False,
            label='Maximum Bedrooms',
            widget=forms.Select(attrs={'class': 'form-select select2'})
        )
        
        # Set up bathroom range dropdowns
        self.fields['min_bathrooms'] = forms.ChoiceField(
            choices=self.BATHROOM_CHOICES,
            required=False,
            label='Minimum Bathrooms',
            widget=forms.Select(attrs={'class': 'form-select select2'})
        )
        self.fields['max_bathrooms'] = forms.ChoiceField(
            choices=self.BATHROOM_CHOICES,
            required=False,
            label='Maximum Bathrooms',
            widget=forms.Select(attrs={'class': 'form-select select2'})
        )

        # Multiple selections
        self.fields['amenities'].widget = forms.CheckboxSelectMultiple()
        self.fields['amenities'].queryset = Amenity.objects.all()
        
        # Remove neighborhood_preferences from rendered fields since we're using custom HTML
        if 'neighborhood_preferences' in self.fields:
            del self.fields['neighborhood_preferences']
        
        # Store neighborhood choices for the template
        from .models import Neighborhood
        self.neighborhood_choices = Neighborhood.objects.all().order_by('name')
        
        # Store building and apartment amenities for the template
        from buildings.models import Amenity as BuildingAmenity
        from apartments.models import ApartmentAmenity
        self.building_amenities = BuildingAmenity.objects.all().order_by('name')
        self.apartment_amenities = ApartmentAmenity.objects.all().order_by('name')
        
        # All fields are optional
        for field_name, field in self.fields.items():
            field.required = False
            field.label_suffix = ''

        # Crispy Forms setup
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'doorway-form'

        self.helper.layout = Layout(
            Fieldset(
                'Housing Needs',
                Row(
                    Column(Field('desired_move_in_date'), css_class='col-md-6 mb-4'),
                    Column(Field('max_rent_budget', template='applicants/currency_field.html'), css_class='col-md-6 mb-4'),
                ),
                HTML('''
                <div class="row mb-4">
                    <div class="col-md-6 mb-4">
                        <label class="form-label">Number of Bedrooms</label>
                        <div class="d-flex align-items-center">
                            <span class="me-2">FROM:</span>
                            <div class="me-3" style="flex: 1;">
                                {{ form.min_bedrooms }}
                            </div>
                            <span class="me-2">TO:</span>
                            <div style="flex: 1;">
                                {{ form.max_bedrooms }}
                            </div>
                        </div>
                    </div>
                    <div class="col-md-6 d-flex align-items-end mb-4">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" name="open_to_roommates" id="{{ form.open_to_roommates.id_for_label }}" style="width: 1.5em; height: 1.5em; transform: scale(1.2);" {% if form.open_to_roommates.value %}checked{% endif %}>
                            <label class="form-check-label ms-3" for="{{ form.open_to_roommates.id_for_label }}" style="font-size: 1.1rem; font-weight: 500; padding-top: 4px;">
                                Open to Roommates?
                            </label>
                        </div>
                    </div>
                </div>
                <div class="row mb-4">
                    <div class="col-md-6 mb-4">
                        <label class="form-label">Number of Bathrooms</label>
                        <div class="d-flex align-items-center">
                            <span class="me-2">FROM:</span>
                            <div class="me-3" style="flex: 1;">
                                {{ form.min_bathrooms }}
                            </div>
                            <span class="me-2">TO:</span>
                            <div style="flex: 1;">
                                {{ form.max_bathrooms }}
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Pets Section -->
                <div class="row mb-2">
                    <div class="col-md-12">
                        <div class="form-check mb-2">
                            <input class="form-check-input pets-checkbox" type="checkbox" id="has_pets" name="has_pets" style="width: 1.5em; height: 1.5em; transform: scale(1.2);">
                            <label class="form-check-label ms-3" for="has_pets" style="font-size: 1.1rem; font-weight: 500; padding-top: 4px;">
                                Pets?
                            </label>
                        </div>
                        
                        <!-- Pet Details Container (initially hidden) -->
                        <div id="pets-container" class="mt-4" style="display: none;">
                            <div class="mb-4">
                                <button type="button" id="add-pet-btn" class="btn btn-sm" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                                    <i class="fas fa-plus"></i> Add Pet
                                </button>
                            </div>
                            <div id="pets-list-container">
                                <!-- Dynamic pet forms will be added here -->
                            </div>
                        </div>
                    </div>
                </div>
                '''),
            ),
            
            Fieldset(
                'HOUSING PREFERENCES',
                HTML('''
                <div class="mb-4">
                    <h6 class="mb-3">Neighborhood Preferences</h6>
                    <p class="text-muted small mb-3">
                        <i class="fas fa-info-circle"></i> Select your preferred neighborhoods and drag them to rank by priority. 
                        Your #1 choice will have the highest priority in our apartment matching algorithm.
                    </p>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <h6 class="text-secondary small mb-2">Available Neighborhoods</h6>
                            <div id="available-neighborhoods" class="neighborhood-list border rounded p-3" style="max-height: 300px; overflow-y: auto;">
                                {% for neighborhood in all_neighborhoods %}
                                <div class="neighborhood-item available" data-neighborhood-id="{{ neighborhood.id }}" draggable="true">
                                    <span class="neighborhood-name">{{ neighborhood.name }}</span>
                                    <i class="fas fa-plus text-success float-end"></i>
                                </div>
                                {% empty %}
                                <p class="text-danger">No neighborhoods found!</p>
                                {% endfor %}
                            </div>
                        </div>
                        
                        <div class="col-md-6">
                            <h6 class="text-secondary small mb-2">Your Ranked Preferences</h6>
                            <div id="selected-neighborhoods" class="neighborhood-list border rounded p-3" style="min-height: 300px;">
                                <div class="text-muted text-center py-4" id="empty-message">
                                    <i class="fas fa-hand-pointer mb-2"></i><br>
                                    Click neighborhoods from the left to add them here, then drag to reorder by preference.
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Hidden inputs to store the ranked preferences -->
                    <div id="neighborhood-preferences-inputs"></div>
                </div>
                '''),
                HTML('''
                <!-- Building Amenities Section -->
                <div class="mb-5">
                    <div class="d-flex align-items-center mb-3">
                        <h5 class="mb-0 me-3">Building Amenities</h5>
                        <small class="text-muted">
                            <i class="fas fa-info-circle"></i> 
                            Set priorities for building-wide amenities. Only select amenities that matter to you.
                        </small>
                    </div>
                    
                    <!-- Priority Legend -->
                    <div class="priority-legend mb-4 p-3 bg-light rounded">
                        <div class="row text-center">
                            <div class="col-md-3">
                                <div class="legend-item">
                                    <div class="legend-color unset-legend"></div>
                                    <small><strong>Don't Care</strong><br>Not important</small>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="legend-item">
                                    <div class="legend-color nice-to-have-legend"></div>
                                    <small><strong>Nice to Have</strong><br>Mild preference</small>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="legend-item">
                                    <div class="legend-color very-important-legend"></div>
                                    <small><strong>Important</strong><br>Strong preference</small>
                                </div>
                            </div>
                            <div class="col-md-3">
                                <div class="legend-item">
                                    <div class="legend-color must-have-legend"></div>
                                    <small><strong>Must Have</strong><br>Deal-breaker if missing</small>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="amenities-grid" id="building-amenities">
                        {% for amenity in all_building_amenities %}
                        <div class="amenity-slider-item unset" data-amenity-id="{{ amenity.id }}" data-amenity-type="building">
                            <div class="amenity-info">
                                <div class="d-flex align-items-center">
                                    {% if amenity.name == "Bike Room" %}
                                        <i class="fa-solid fa-bicycle me-2 text-warning"></i>
                                    {% elif amenity.name == "Business center" %}
                                        <i class="fa-solid fa-briefcase me-2 text-warning"></i>
                                    {% elif amenity.name == "Children's Play Room" %}
                                        <i class="fa-solid fa-child me-2 text-warning"></i>
                                    {% elif amenity.name == "Cold Storage" %}
                                        <i class="fa-regular fa-snowflake me-2 text-warning"></i>
                                    {% elif amenity.name == "Concierge" %}
                                        <i class="fa-solid fa-bell-concierge me-2 text-warning"></i>
                                    {% elif amenity.name == "Courtyard" %}
                                        <i class="fa-solid fa-tree me-2 text-warning"></i>
                                    {% elif amenity.name == "Covered parking" %}
                                        <i class="fa-solid fa-square-parking me-2 text-warning"></i>
                                    {% elif amenity.name == "Doorman" %}
                                        <i class="fa-solid fa-door-closed me-2 text-warning"></i>
                                    {% elif amenity.name == "Elevator" %}
                                        <i class="fa-solid fa-arrows-up-down me-2 text-warning"></i>
                                    {% elif amenity.name == "Fitness Center" %}
                                        <i class="fa-solid fa-dumbbell me-2 text-warning"></i>
                                    {% elif amenity.name == "Gym" %}
                                        <i class="fa-solid fa-dumbbell me-2 text-warning"></i>
                                    {% elif amenity.name == "Garage Parking" %}
                                        <i class="fa-solid fa-square-parking me-2 text-warning"></i>
                                    {% elif amenity.name == "Garbage chute" %}
                                        <i class="fa-solid fa-trash me-2 text-warning"></i>
                                    {% elif amenity.name == "Garden" %}
                                        <i class="fa-solid fa-seedling me-2 text-warning"></i>
                                    {% elif amenity.name == "Green building" %}
                                        <i class="fa-solid fa-leaf me-2 text-warning"></i>
                                    {% elif amenity.name == "Guarantors Welcome" %}
                                        <i class="fa-regular fa-file-signature me-2 text-warning"></i>
                                    {% elif amenity.name == "Laundry In Building" %}
                                        <i class="fa-solid fa-soap me-2 text-warning"></i>
                                    {% elif amenity.name == "Live In Super" %}
                                        <i class="fa-solid fa-screwdriver-wrench me-2 text-warning"></i>
                                    {% elif amenity.name == "Locker Rooms" %}
                                        <i class="fa-solid fa-lock me-2 text-warning"></i>
                                    {% elif amenity.name == "Media Room" %}
                                        <i class="fa-solid fa-tv me-2 text-warning"></i>
                                    {% elif amenity.name == "Non Smoking Building" %}
                                        <i class="fa-solid fa-ban-smoking me-2 text-warning"></i>
                                    {% elif amenity.name == "On site super" %}
                                        <i class="fa-solid fa-screwdriver-wrench me-2 text-warning"></i>
                                    {% elif amenity.name == "Outdoor Spaces" %}
                                        <i class="fa-solid fa-umbrella-beach me-2 text-warning"></i>
                                    {% elif amenity.name == "Package Room" %}
                                        <i class="fa-solid fa-box me-2 text-warning"></i>
                                    {% elif amenity.name == "Parking" %}
                                        <i class="fa-solid fa-square-parking me-2 text-warning"></i>
                                    {% elif amenity.name == "Pet spa" %}
                                        <i class="fa-solid fa-bath me-2 text-warning"></i>
                                    {% elif amenity.name == "Pool" %}
                                        <i class="fa-solid fa-water-ladder me-2 text-warning"></i>
                                    {% elif amenity.name == "Recreation" %}
                                        <i class="fa-solid fa-table-tennis-paddle-ball me-2 text-warning"></i>
                                    {% elif amenity.name == "Resident Lounge" %}
                                        <i class="fa-solid fa-couch me-2 text-warning"></i>
                                    {% elif amenity.name == "Roof Access" %}
                                        <i class="fa-solid fa-arrow-up-from-ground-water me-2 text-warning"></i>
                                    {% elif amenity.name == "Roof Deck" %}
                                        <i class="fa-solid fa-arrow-up-from-ground-water me-2 text-warning"></i>
                                    {% elif amenity.name == "Screening room" %}
                                        <i class="fa-solid fa-tv me-2 text-warning"></i>
                                    {% elif amenity.name == "Security cameras" %}
                                        <i class="fa-solid fa-video me-2 text-warning"></i>
                                    {% elif amenity.name == "Smoke free property" %}
                                        <i class="fa-solid fa-ban-smoking me-2 text-warning"></i>
                                    {% elif amenity.name == "Storage" %}
                                        <i class="fa-solid fa-box-archive me-2 text-warning"></i>
                                    {% elif amenity.name == "Valet" %}
                                        <i class="fa-solid fa-key me-2 text-warning"></i>
                                    {% elif amenity.name == "Verizon Fios" %}
                                        <i class="fa-solid fa-tower-broadcast me-2 text-warning"></i>
                                    {% elif amenity.name == "Virtual Doorman" %}
                                        <i class="fa-solid fa-tablet-screen-button me-2 text-warning"></i>
                                    {% elif amenity.name == "Wheelchair Access" %}
                                        <i class="fa-solid fa-wheelchair me-2 text-warning"></i>
                                    {% elif amenity.name == "Yoga studio" %}
                                        <i class="fa-solid fa-spa me-2 text-warning"></i>
                                    {% else %}
                                        <i class="fa-solid fa-check-circle me-2 text-warning"></i>
                                    {% endif %}
                                    <span class="amenity-name">{{ amenity.name }}</span>
                                </div>
                                <span class="priority-label text-muted"></span>
                            </div>
                            <div class="slider-container mt-2">
                                <input type="range" 
                                       min="0" 
                                       max="3" 
                                       value="0" 
                                       step="1" 
                                       class="amenity-slider unset" 
                                       name="building_amenity_{{ amenity.id }}"
                                       data-amenity-id="{{ amenity.id }}"
                                       data-amenity-type="building"
                                       data-amenity-name="{{ amenity.name }}"
                                       data-existing-value="0">
                                <div class="slider-labels">
                                    <span class="slider-label-left">Don't Care</span>
                                    <span class="slider-label-right">Must Have</span>
                                </div>
                            </div>
                        </div>
                        {% empty %}
                        <p class="text-muted">No building amenities available</p>
                        {% endfor %}
                    </div>
                </div>
                
                <!-- Apartment Amenities Section -->
                <div class="mb-5">
                    <div class="d-flex align-items-center mb-3">
                        <h5 class="mb-0 me-3">Apartment Features</h5>
                        <small class="text-muted">
                            <i class="fas fa-info-circle"></i> 
                            Set priorities for apartment-specific features. Only select features that matter to you.
                        </small>
                    </div>
                    
                    <div class="amenities-grid" id="apartment-amenities">
                        {% for amenity in all_apartment_amenities %}
                        <div class="amenity-slider-item unset" data-amenity-id="{{ amenity.id }}" data-amenity-type="apartment">
                            <div class="amenity-info">
                                <span class="amenity-name">{{ amenity.name }}</span>
                                <span class="priority-label text-muted"></span>
                            </div>
                            <div class="slider-container mt-2">
                                <input type="range" 
                                       min="0" 
                                       max="3" 
                                       value="0" 
                                       step="1" 
                                       class="amenity-slider unset" 
                                       name="apartment_amenity_{{ amenity.id }}"
                                       data-amenity-id="{{ amenity.id }}"
                                       data-amenity-type="apartment"
                                       data-amenity-name="{{ amenity.name }}"
                                       data-existing-value="0">
                                <div class="slider-labels">
                                    <span class="slider-label-left">Don't Care</span>
                                    <span class="slider-label-right">Must Have</span>
                                </div>
                            </div>
                        </div>
                        {% empty %}
                        <p class="text-muted">No apartment amenities available</p>
                        {% endfor %}
                    </div>
                </div>
                '''),
            ),
            
            # Navigation Buttons
            Div(
                HTML('<a href="{% url \'profile_step1\' %}" class="btn btn-doorway-secondary btn-lg me-3">← Previous</a>'),
                Submit('housing_submit', 'Save & Continue', css_class='btn btn-doorway-primary btn-lg me-3'),
                HTML('<a href="{% url \'profile_step3\' %}" class="btn btn-outline-secondary btn-lg">Skip</a>'),
                css_class='text-center mt-4'
            )
        )


class ApplicantEmploymentForm(forms.ModelForm):
    """Step 3: Income & Employment Form"""
    
    # Add extra form fields not in the model
    income_source = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    average_annual_income = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control currency-field',
            'step': '0.01',
            'placeholder': '$0.00'
        })
    )
    
    class Meta:
        model = Applicant
        fields = [
            'employment_status', 
            # Employment fields
            'company_name', 'position', 'annual_income', 'supervisor_name', 'supervisor_email', 
            'supervisor_phone', 'currently_employed', 'employment_start_date', 'employment_end_date',
            # Student fields
            'school_name', 'year_of_graduation', 'school_address', 'school_phone',
        ]
        widgets = {
            'employment_status': forms.Select(attrs={'class': 'form-select select2'}),
            # New employment field widgets
            'annual_income': forms.NumberInput(attrs={
                'class': 'form-control currency-field',
                'step': '0.01',
                'placeholder': '75000.00',
                'min': '0'
            }),
            'supervisor_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(555) 555-5555'}),
            'employment_start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'employment_end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            # Legacy field widgets (keep for backward compatibility)
            'monthly_income': forms.NumberInput(attrs={
                'class': 'form-control currency-field',
                'step': '0.01',
                'placeholder': '5000.00',
                'min': '0'
            }),
            # Student field widgets
            'school_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123 University Ave, College Town, NY 12345'}),
            'school_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(555) 555-5555'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # All fields are optional
        for field_name, field in self.fields.items():
            field.required = False
            field.label_suffix = ''
            
        # Customize specific field labels and choices
        self.fields['employment_status'].label = 'Which best describes you?'
        self.fields['employment_status'].required = False
        self.fields['employment_status'].choices = [
            ('', 'Select an option...'),
            ('student', 'I am a student'),
            ('employed', 'I am employed'),
            ('other', 'Other'),
        ]
        self.fields['employment_status'].initial = ''

        # Crispy Forms setup
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'doorway-form'

        self.helper.layout = Layout(
            Fieldset(
                'Employment Status',
                Field('employment_status', css_class='employment-status-dropdown mb-4 select2'),
            ),
            
            HTML('<div id="employed-fields" style="display: none;">'),
            Fieldset(
                'Employment Information',
                Row(
                    Column('company_name', css_class='col-md-6'),
                    Column('position', css_class='col-md-6'),
                ),
                Row(
                    Column(Field('annual_income', template='applicants/currency_income_field.html'), css_class='col-md-6'),
                    Column('supervisor_name', css_class='col-md-6'),
                ),
                Row(
                    Column('supervisor_email', css_class='col-md-6'),
                    Column(Field('supervisor_phone', placeholder="(555) 555-5555"), css_class='col-md-6'),
                ),
                HTML('''
                <div class="row mb-3">
                    <div class="col-md-12">
                        <div class="form-check">
                            <input class="form-check-input currently-employed-checkbox" type="checkbox" name="currently_employed" id="{{ form.currently_employed.id_for_label }}" {% if form.currently_employed.value %}checked{% endif %} style="width: 1.25em; height: 1.25em;">
                            <label class="form-check-label ms-2" for="{{ form.currently_employed.id_for_label }}" style="font-size: 1.1rem; font-weight: 500;">
                                I am currently employed here
                            </label>
                        </div>
                    </div>
                </div>
                
                <div id="employment-dates" class="row mb-3">
                    <div class="col-md-6" id="start-date-field">
                        <label class="form-label">Start Date</label>
                        {{ form.employment_start_date }}
                    </div>
                    <div class="col-md-6" id="end-date-field" style="display: none;">
                        <label class="form-label">End Date</label>
                        {{ form.employment_end_date }}
                    </div>
                </div>
                '''),
                HTML('''
                <div class="mt-3">
                    <button type="button" id="add-job-btn-employed" class="btn btn-sm me-2" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Job
                    </button>
                    <button type="button" id="add-income-btn-employed" class="btn btn-sm me-2" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Income Source
                    </button>
                    <button type="button" id="add-asset-btn-employed" class="btn btn-sm" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Asset
                    </button>
                </div>
                '''),
            ),
            
            HTML('''
            <div id="jobs-container-employed" style="display: none;">
                <h5 class="mb-3">Additional Employment</h5>
                <div id="jobs-list-employed"></div>
            </div>
            '''),
            
            HTML('''
            <div id="income-container-employed" style="display: none;">
                <h5 class="mb-3">Income Sources</h5>
                <div id="income-list-employed"></div>
            </div>
            '''),
            
            HTML('''
            <div id="assets-container-employed" style="display: none;">
                <h5 class="mb-3">Assets</h5>
                <div id="assets-list-employed"></div>
            </div>
            '''),
            
            HTML('</div>'),
            
            HTML('<div id="student-fields" style="display: none;">'),
            Fieldset(
                'School Information',
                Row(
                    Column('school_name', css_class='col-md-6'),
                    Column(Field('year_of_graduation', placeholder="2025"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('school_address', placeholder="123 University Ave, College Town, NY 12345"), css_class='col-md-6'),
                    Column(Field('school_phone', placeholder="(555) 555-5555"), css_class='col-md-6'),
                ),
                HTML('''
                <div class="mt-3">
                    <button type="button" id="add-job-btn" class="btn btn-sm me-2" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Job
                    </button>
                    <button type="button" id="add-income-btn" class="btn btn-sm me-2" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Income Source
                    </button>
                    <button type="button" id="add-asset-btn" class="btn btn-sm" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                        <i class="fas fa-plus"></i> Add Asset
                    </button>
                </div>
                '''),
            ),
            
            HTML('''
            <div id="jobs-container" style="display: none;">
                <h5 class="mb-3">Employment</h5>
                <div id="jobs-list"></div>
            </div>
            '''),
            
            HTML('''
            <div id="income-container" style="display: none;">
                <h5 class="mb-3">Income Sources</h5>
                <div id="income-list"></div>
            </div>
            '''),
            
            HTML('''
            <div id="assets-container" style="display: none;">
                <h5 class="mb-3">Assets</h5>
                <div id="assets-list"></div>
            </div>
            '''),
            
            HTML('</div>'),
            
            HTML('<div id="other-fields" style="display: none;">'),
            HTML('''
            <div class="mt-3">
                <button type="button" id="add-income-btn-other" class="btn btn-sm me-2" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                    <i class="fas fa-plus"></i> Add Income Source
                </button>
                <button type="button" id="add-asset-btn-other" class="btn btn-sm" style="background-color: #ffcc00; color: #000000; border: 1px solid #ffcc00;">
                    <i class="fas fa-plus"></i> Add Asset
                </button>
            </div>
            '''),
            
            HTML('''
            <div id="income-container-other" style="display: none;">
                <h5 class="mb-3">Income Sources</h5>
                <div id="income-list-other"></div>
            </div>
            '''),
            
            HTML('''
            <div id="assets-container-other" style="display: none;">
                <h5 class="mb-3">Assets</h5>
                <div id="assets-list-other"></div>
            </div>
            '''),
            
            HTML('</div>'),
            
            # Navigation Buttons
            Div(
                HTML('<a href="{% url \'profile_step2\' %}" class="btn btn-doorway-secondary btn-lg me-3">← Previous</a>'),
                Submit('employment_submit', 'Complete Profile', css_class='btn btn-success btn-lg me-3'),
                HTML('<a href="{% url \'applicant_dashboard\' %}" class="btn btn-outline-secondary btn-lg">Skip</a>'),
                css_class='text-center mt-4'
            )
        )


# Original single-page form (keep for backward compatibility)
class ApplicantForm(forms.ModelForm):
    class Meta:
        model = Applicant
        fields = [
            'first_name', 'last_name', 'date_of_birth',
            'phone_number', 'email',
            'street_address_1', 'street_address_2', 'city', 'state', 'zip_code',
            'housing_status', 'current_landlord_name', 'current_landlord_phone', 'current_landlord_email',
            'desired_move_in_date', 'number_of_bedrooms', 'number_of_bathrooms', 'max_rent_budget', 'open_to_roommates',
            'driver_license_number', 'driver_license_state',
            'amenities', 'neighborhood_preferences',
            'emergency_contact_name', 'emergency_contact_relationship', 'emergency_contact_phone',
            'employment_status', 'school_name', 'year_of_graduation', 'school_address', 'school_phone',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'desired_move_in_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            # Currency fields with same restrictions as buildings form
            'max_rent_budget': forms.NumberInput(attrs={
                'class': 'form-control currency-field',
                'step': '0.01',
                'placeholder': '2500.00',
                'min': '0'
            }),
            'employment_status': forms.Select(attrs={'class': 'form-select select2'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Allow decimal values for bedrooms and bathrooms
        self.fields['number_of_bedrooms'].widget = forms.NumberInput(attrs={'step': '0.5', 'class': 'form-control'})
        self.fields['number_of_bathrooms'].widget = forms.NumberInput(attrs={'step': '0.5', 'class': 'form-control'})

        # Multiple selections
        self.fields['amenities'].widget = forms.CheckboxSelectMultiple()
        self.fields['amenities'].queryset = Amenity.objects.all()

        self.fields['neighborhood_preferences'].widget = forms.CheckboxSelectMultiple()
        self.fields['neighborhood_preferences'].queryset = Neighborhood.objects.all()
        
        # Only first_name, last_name, and email are required
        # Mark all other fields as not required
        required_fields = ['first_name', 'last_name', 'email']
        for field_name, field in self.fields.items():
            if field_name not in required_fields:
                field.required = False

        # Crispy Forms setup - matching buildings form style
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.form_class = 'doorway-form'
        
        # Remove label suffixes like buildings form
        for field_name, field in self.fields.items():
            field.label_suffix = ''
            if field.required:
                field.widget.attrs['required'] = 'required'

        self.helper.layout = Layout(
            Fieldset(
                'Basic Info',
                Row(
                    Column(Field('first_name', placeholder="First Name"), css_class='col-md-6'),
                    Column(Field('last_name', placeholder="Last Name"), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('phone_number', placeholder="(555) 555-5555"), css_class='col-md-6'),
                    Column('email', css_class='col-md-6'),
                ),
                HTML('<h6 class="mt-4 mb-3 text-secondary">Current Address</h6>'),
                Row(
                    Column('street_address_1', css_class='col-md-8'),
                    Column('street_address_2', css_class='col-md-4'),
                ),
                Row(
                    Column('city', css_class='col-md-5'),
                    Column('state', css_class='col-md-3'),
                    Column('zip_code', css_class='col-md-4'),
                ),
                HTML('''
                <div class="form-check mb-3">
                    <input class="form-check-input" type="checkbox" id="is_rental_checkbox" name="is_rental_checkbox">
                    <label class="form-check-label" for="is_rental_checkbox">
                        Is this a Rental?
                    </label>
                </div>
                '''),
                Field('housing_status', type="hidden"),
                Div(
                    Row(
                        Column(Field('current_landlord_name', placeholder="Landlord's Name"), css_class='col-md-4'),
                        Column(Field('current_landlord_phone', placeholder="(555) 555-5555"), css_class='col-md-4'),
                        Column(Field('current_landlord_email', placeholder="Landlord's Email"), css_class='col-md-4'),
                    ),
                    css_id='landlord_fields',
                    css_class='d-none'
                ),
                HTML('''
                <!-- Previous Address Section -->
                <div class="mt-4 mb-4">
                    <div class="d-flex justify-content-between align-items-center mb-3">
                        <h6 class="fw-bold text-secondary mb-0" style="font-size: 1rem;">Previous Addresses</h6>
                        <button type="button" id="add-previous-address-btn" class="btn btn-outline-primary btn-sm">
                            <i class="fas fa-plus"></i> Add Previous Address
                        </button>
                    </div>
                    <p class="text-muted small mb-3">Add up to 4 previous addresses to help with your rental history.</p>
                    <div id="previous-addresses-container">
                        <!-- Dynamic previous address forms will be added here -->
                    </div>
                </div>
                '''),
                HTML('<h6 class="mt-4 mb-3 text-secondary">Identification</h6>'),
                Row(
                    Column(Field('date_of_birth', placeholder=""), css_class='col-md-6'),
                    Column(css_class='col-md-6'),
                ),
                Row(
                    Column(Field('driver_license_number', placeholder="Driver's License Number"), css_class='col-md-6'),
                    Column('driver_license_state', css_class='col-md-6'),
                ),
                HTML('<h6 class="mt-4 mb-3 text-secondary">Emergency Contact</h6>'),
                Row(
                    Column(Field('emergency_contact_name', placeholder="Full Name"), css_class='col-md-6'),
                    Column(Field('emergency_contact_phone', placeholder="(555) 555-5555"), css_class='col-md-6'),
                ),
                Field('emergency_contact_relationship', placeholder="Relationship (e.g., Friend, Sibling)"),
            ),
            Fieldset(
                'Housing Needs and Preferences',
                Row(
                    Column(Field('desired_move_in_date'), css_class='col-md-6'),
                    Column(Field('max_rent_budget', template='applicants/currency_field.html'), css_class='col-md-6'),
                ),
                Row(
                    Column(Field('number_of_bedrooms'), css_class='col-md-4'),
                    Column(Field('number_of_bathrooms'), css_class='col-md-4'),
                    Column('open_to_roommates', css_class='col-md-4'),
                ),
                HTML('<h6 class="mt-4 mb-3 text-secondary">Preferences</h6>'),
                InlineCheckboxes('neighborhood_preferences'),
                InlineCheckboxes('amenities'),
            ),
            Fieldset(
                'Employment & Student Information',
                Row(
                    Column('employment_status', css_class='col-md-6'),
                    css_class='mb-3'
                ),
                # Student fields
                Row(
                    Column('school_name', css_class='col-md-6'),
                    Column('year_of_graduation', css_class='col-md-6'),
                ),
                'school_address',
                'school_phone',
                # Dynamic employment sections
                HTML('{% include "applicants/employment_sections.html" %}'),
            ),
            Div(
                Submit('applicant_submit', 'Save Profile', css_class='btn btn-doorway-primary btn-lg me-3'),
                HTML('<a href="{% url \'applicant_dashboard\' %}" class="btn btn-doorway-secondary btn-lg">Cancel</a>'),
                css_class='text-center mt-4'
            )
        )


class ApplicantPhotoForm(forms.ModelForm):
    image = CloudinaryFileField()

    class Meta:
        model = ApplicantPhoto
        fields = ['image']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'


class PetForm(forms.ModelForm):
    class Meta:
        model = Pet
        fields = ['pet_type', 'quantity', 'description']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'

        self.helper.layout = Layout(
            Fieldset(
                'Pet Information',
                Row(
                    Column(Field('pet_type'), css_class='col-md-6'),
                    Column(Field('quantity', placeholder="e.g., 1"), css_class='col-md-6'),
                ),
                Field('description'),
            ),
            Submit('pet_submit', 'Save Pet', css_class='btn btn-primary'),
        )


class PetPhotoForm(forms.ModelForm):
    image = CloudinaryFileField()

    class Meta:
        model = PetPhoto
        fields = ['image']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper(self)
        self.helper.form_method = 'post'



FAKE_USERS = [
    ("Meron", "Meron"),
    ("Eden", "Eden"),
    ("Asaf", "Asaf"),
    ("Fabron", "Fabron"),
]



from django import forms
from .models import InteractionLog

FAKE_USERS = [
    ("meron", "Meron"),
    ("eden", "Eden"),
    ("asaf", "Asaf"),
    ("fabron", "Fabron"),
]

class InteractionLogForm(forms.ModelForm):
    file = forms.FileField(required=False, widget=forms.FileInput(attrs={"class": "form-control"}))  # ✅ Simple file upload
    notify_users = forms.MultipleChoiceField(
        choices=FAKE_USERS,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Notify Users",
    )  # ✅ Fake checkboxes for notifications

    class Meta:
        model = InteractionLog
        fields = ["note", "file", "notify_users"]  # ✅ Added notify_users
        widgets = {
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Enter interaction details..."}),
        }


