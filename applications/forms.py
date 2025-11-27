from django import forms
from .models import Application, RequiredDocumentType, PersonalInfoData, PreviousAddress, IncomeData
from applicants.models import Applicant
from apartments.models import Apartment

class ApplicationForm(forms.ModelForm):
    required_documents = forms.MultipleChoiceField(
        choices=RequiredDocumentType.choices,
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    # ✅ Fields from Applicant Model to Pre-Fill
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    date_of_birth = forms.DateField(required=False, widget=forms.TextInput(attrs={"type": "date"}))
    phone_number = forms.CharField(required=False)
    email = forms.EmailField(required=False)

    street_address_1 = forms.CharField(required=False)
    street_address_2 = forms.CharField(required=False)
    city = forms.CharField(required=False)
    state = forms.ChoiceField(choices=Applicant.STATE_CHOICES, required=False)
    zip_code = forms.CharField(required=False)

    length_at_current_address = forms.CharField(required=False, label="How long have you lived here?")
    housing_status = forms.ChoiceField(
        choices=[("rent", "Rent"), ("own", "Own")],
        required=False,
        widget=forms.RadioSelect,
        label="Do you rent or own?"
    )
    current_landlord_name = forms.CharField(required=False, label="Landlord/Property Manager Name")
    current_landlord_phone = forms.CharField(required=False, label="Landlord Phone")
    current_landlord_email = forms.EmailField(required=False, label="Landlord Email")
    reason_for_moving = forms.CharField(widget=forms.Textarea, required=False, label="Reason for Moving")
    monthly_rent = forms.DecimalField(
        required=False, 
        label="Monthly Rent ($)", 
        max_digits=10, 
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control currency-field',
            'step': '0.01',
            'placeholder': '2500.00',
            'min': '0'
        })
    )


    driver_license_number = forms.CharField(required=False)
    driver_license_state = forms.ChoiceField(choices=Applicant.STATE_CHOICES, required=False)

    # ✅ Employment Status
    employment_status = forms.ChoiceField(
        choices=[
            ('', 'Select an option...'),
            ('student', 'I am a student'),
            ('employed', 'I am employed'),
            ('other', 'Other'),
        ],
        required=False,
        label="Employment Status"
    )

    # ✅ Main Employment Fields (for primary job or employment status)
    company_name = forms.CharField(required=False, label="Company Name")
    position = forms.CharField(required=False, label="Position/Job Title")
    annual_income = forms.DecimalField(
        required=False, 
        label="Annual Income ($)", 
        max_digits=12, 
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control currency-field',
            'step': '0.01',
            'placeholder': '0.00',
            'min': '0'
        })
    )
    supervisor_name = forms.CharField(required=False, label="Supervisor Name")
    supervisor_email = forms.EmailField(required=False, label="Supervisor Email")
    supervisor_phone = forms.CharField(required=False, label="Supervisor Phone")
    currently_employed = forms.BooleanField(required=False, label="Currently employed here")
    employment_start_date = forms.DateField(required=False, widget=forms.TextInput(attrs={"type": "date"}), label="Start Date")
    employment_end_date = forms.DateField(required=False, widget=forms.TextInput(attrs={"type": "date"}), label="End Date")

    # ✅ Student Fields
    school_name = forms.CharField(required=False, label="School Name")
    year_of_graduation = forms.CharField(required=False, label="Year of Graduation", max_length=4)
    school_address = forms.CharField(required=False, label="School Address", widget=forms.Textarea(attrs={'rows': 2}))
    school_phone = forms.CharField(required=False, label="School Phone")

    # ✅ Emergency Contact Fields
    emergency_contact_name = forms.CharField(required=False, label="Emergency Contact Name")
    emergency_contact_relationship = forms.CharField(required=False, label="Relationship")
    emergency_contact_phone = forms.CharField(required=False, label="Emergency Contact Phone")


    # ✅ Fields from Apartment Model to Pre-Fill
    rent_price = forms.DecimalField(
        required=False, 
        label="Rent Price ($)", 
        max_digits=10, 
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control currency-field',
            'step': '0.01',
            'placeholder': '3000.00',
            'min': '0'
        })
    )
    bedrooms = forms.DecimalField(required=False, label="Bedrooms", max_digits=3, decimal_places=1)
    bathrooms = forms.DecimalField(required=False, label="Bathrooms", max_digits=3, decimal_places=1)


    # Manual address fields for applications without apartment relationships
    manual_building_name = forms.CharField(
        required=False,
        label="Building Name",
        help_text="Enter building name if not in our system",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., The Manhattan Building'})
    )
    manual_building_address = forms.CharField(
        required=False,
        label="Building Address *",
        help_text="Enter full building address",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '123 Main Street, New York, NY 10001'})
    )
    manual_unit_number = forms.CharField(
        required=False,
        label="Unit Number *",
        help_text="Enter apartment/unit number",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 3A, Unit 15'})
    )

    class Meta:
        model = Application
        fields = [
            "apartment", "applicant", "required_documents",
            "manual_building_name", "manual_building_address", "manual_unit_number",
            "first_name", "last_name", "date_of_birth", "phone_number", "email",
            "street_address_1", "street_address_2", "city", "state", "zip_code",
            "driver_license_number", "driver_license_state",
            "employment_status", "company_name", "position", "annual_income",
            "supervisor_name", "supervisor_email", "supervisor_phone",
            "currently_employed", "employment_start_date", "employment_end_date",
            "school_name", "year_of_graduation", "school_address", "school_phone",
            "emergency_contact_name", "emergency_contact_relationship", "emergency_contact_phone",
            "length_at_current_address", "housing_status", "current_landlord_name",
            "current_landlord_phone", "current_landlord_email", "reason_for_moving", "monthly_rent",
            "rent_price", "bedrooms", "bathrooms"
        ]


    def __init__(self, *args, **kwargs):
        applicant = kwargs.pop("applicant", None)  # ✅ Remove before calling super()
        apartment = kwargs.pop("apartment", None)
        user = kwargs.pop("user", None)  # Current logged in user (broker)
        super().__init__(*args, **kwargs)
        self.user = user  # Store user for validation in clean()

        # ✅ Make apartment field optional with empty label
        self.fields["apartment"].queryset = Apartment.objects.all()
        self.fields["apartment"].widget.attrs.update({"class": "form-control"})
        self.fields["apartment"].required = False
        self.fields["apartment"].empty_label = "Select apartment (or use manual fields below)"

        self.fields["applicant"].queryset = Applicant.objects.all()
        self.fields["applicant"].widget.attrs.update({"class": "form-control"})
        self.fields["applicant"].required = False
        self.fields["applicant"].empty_label = "Select applicant (optional - can be added later)"

        self.fields["required_documents"].widget.attrs.update({"class": "form-check"})

        # ✅ Use intelligent pre-filling service
        if applicant:
            from .services import ApplicationDataService
            prefill_data = ApplicationDataService.get_prefill_data_for_applicant(applicant)
            
            # Apply pre-filled data to form fields
            for field_name, value in prefill_data.items():
                if field_name in self.fields:
                    self.fields[field_name].initial = value
            
            # Set the applicant field
            self.fields["applicant"].initial = applicant
            
            # Add a note if data was pre-filled from previous applications
            if prefill_data:
                self.fields["first_name"].help_text = "Pre-filled from applicant profile"
            
            # Add dynamic fields for multiple jobs, income sources, and assets
            self._add_dynamic_employment_fields(applicant)

        # ✅ If an apartment is pre-selected, pre-fill its data
        if apartment:
            try:
                self.fields["apartment"].initial = apartment
                self.fields["rent_price"].initial = apartment.rent_price
                self.fields["bedrooms"].initial = apartment.bedrooms
                self.fields["bathrooms"].initial = apartment.bathrooms
            except Apartment.DoesNotExist:
                pass  # Ignore if apartment ID is invalid

    def clean(self):
        cleaned_data = super().clean()
        apartment = cleaned_data.get('apartment')
        manual_address = cleaned_data.get('manual_building_address')
        manual_unit = cleaned_data.get('manual_unit_number')
        
        # Check if the user is a broker (passed in __init__)
        is_broker = False
        if hasattr(self, 'user') and self.user:
             is_broker = getattr(self.user, 'is_broker', False)

        # STRICT MODE: Brokers MUST select an apartment
        if is_broker and not apartment:
            raise forms.ValidationError("Brokers must select an existing apartment. Manual address entry is not permitted.")

        # Either apartment OR manual fields must be provided (for non-brokers)
        if not apartment and not (manual_address and manual_unit):
            raise forms.ValidationError("Please either select an apartment from our database or enter manual address information.")
        
        # If manual fields are provided, they should be complete
        if (manual_address or manual_unit) and not (manual_address and manual_unit):
            if not manual_address:
                self.add_error('manual_building_address', 'Building address is required when using manual entry.')
            if not manual_unit:
                self.add_error('manual_unit_number', 'Unit number is required when using manual entry.')
        
        return cleaned_data

    def _add_dynamic_employment_fields(self, applicant):
        """Add dynamic form fields for multiple jobs, income sources, and assets from applicant profile"""
        if not applicant:
            return
            
        # Add multiple jobs from applicant profile
        jobs = applicant.jobs.all()
        for i, job in enumerate(jobs, 1):
            # Add job fields dynamically
            self.fields[f'job_company_{i}'] = forms.CharField(
                required=False,
                initial=job.company_name,
                label=f'Job {i} - Company Name'
            )
            self.fields[f'job_position_{i}'] = forms.CharField(
                required=False,
                initial=job.position,
                label=f'Job {i} - Position'
            )
            self.fields[f'job_income_{i}'] = forms.DecimalField(
                required=False,
                initial=job.annual_income,
                label=f'Job {i} - Annual Income ($)',
                max_digits=12,
                decimal_places=2,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control currency-field',
                    'step': '0.01',
                    'placeholder': '0.00'
                })
            )
            self.fields[f'job_supervisor_{i}'] = forms.CharField(
                required=False,
                initial=job.supervisor_name,
                label=f'Job {i} - Supervisor Name'
            )
            self.fields[f'job_supervisor_email_{i}'] = forms.EmailField(
                required=False,
                initial=job.supervisor_email,
                label=f'Job {i} - Supervisor Email'
            )
            self.fields[f'job_supervisor_phone_{i}'] = forms.CharField(
                required=False,
                initial=job.supervisor_phone,
                label=f'Job {i} - Supervisor Phone'
            )
            self.fields[f'job_current_{i}'] = forms.BooleanField(
                required=False,
                initial=job.currently_employed,
                label=f'Job {i} - Currently Employed Here'
            )
            self.fields[f'job_start_date_{i}'] = forms.DateField(
                required=False,
                initial=job.employment_start_date,
                label=f'Job {i} - Start Date',
                widget=forms.TextInput(attrs={"type": "date"})
            )
            self.fields[f'job_end_date_{i}'] = forms.DateField(
                required=False,
                initial=job.employment_end_date,
                label=f'Job {i} - End Date',
                widget=forms.TextInput(attrs={"type": "date"})
            )

        # Add multiple income sources from applicant profile  
        income_sources = applicant.income_sources.all()
        for i, income in enumerate(income_sources, 1):
            self.fields[f'income_source_{i}'] = forms.CharField(
                required=False,
                initial=income.income_source,
                label=f'Income Source {i} - Type'
            )
            self.fields[f'income_amount_{i}'] = forms.DecimalField(
                required=False,
                initial=income.average_annual_income,
                label=f'Income Source {i} - Annual Amount ($)',
                max_digits=12,
                decimal_places=2,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control currency-field',
                    'step': '0.01',
                    'placeholder': '0.00'
                })
            )

        # Add multiple assets from applicant profile
        assets = applicant.assets.all()
        for i, asset in enumerate(assets, 1):
            self.fields[f'asset_name_{i}'] = forms.CharField(
                required=False,
                initial=asset.asset_name,
                label=f'Asset {i} - Name/Type'
            )
            self.fields[f'asset_balance_{i}'] = forms.DecimalField(
                required=False,
                initial=asset.account_balance,
                label=f'Asset {i} - Balance ($)',
                max_digits=12,
                decimal_places=2,
                widget=forms.NumberInput(attrs={
                    'class': 'form-control currency-field',
                    'step': '0.01',
                    'placeholder': '0.00'
                })
            )

        # Add previous addresses from applicant profile
        previous_addresses = applicant.previous_addresses.all()
        for i, prev_addr in enumerate(previous_addresses, 1):
            self.fields[f'prev_street_address_1_{i}'] = forms.CharField(
                required=False,
                initial=prev_addr.street_address_1,
                label=f'Previous Address {i} - Street Address'
            )
            self.fields[f'prev_street_address_2_{i}'] = forms.CharField(
                required=False,
                initial=prev_addr.street_address_2,
                label=f'Previous Address {i} - Apt/Unit'
            )
            self.fields[f'prev_city_{i}'] = forms.CharField(
                required=False,
                initial=prev_addr.city,
                label=f'Previous Address {i} - City'
            )
            self.fields[f'prev_state_{i}'] = forms.CharField(
                required=False,
                initial=prev_addr.state,
                label=f'Previous Address {i} - State'
            )
            self.fields[f'prev_zip_code_{i}'] = forms.CharField(
                required=False,
                initial=prev_addr.zip_code,
                label=f'Previous Address {i} - ZIP'
            )
            self.fields[f'prev_length_at_address_{i}'] = forms.CharField(
                required=False,
                initial=prev_addr.length_at_address,
                label=f'Previous Address {i} - Length of Stay'
            )
            self.fields[f'prev_housing_status_{i}'] = forms.ChoiceField(
                choices=[('rent', 'Rent'), ('own', 'Own')],
                required=False,
                initial=prev_addr.housing_status,
                label=f'Previous Address {i} - Housing Status'
            )
            if prev_addr.housing_status == 'rent':
                self.fields[f'prev_landlord_name_{i}'] = forms.CharField(
                    required=False,
                    initial=prev_addr.landlord_name,
                    label=f'Previous Address {i} - Landlord Name'
                )
                self.fields[f'prev_landlord_phone_{i}'] = forms.CharField(
                    required=False,
                    initial=prev_addr.landlord_phone,
                    label=f'Previous Address {i} - Landlord Phone'
                )
                self.fields[f'prev_landlord_email_{i}'] = forms.EmailField(
                    required=False,
                    initial=prev_addr.landlord_email,
                    label=f'Previous Address {i} - Landlord Email'
                )

    def save(self, commit=True):
        application = super().save(commit=False)

        application.required_documents = self.cleaned_data.get("required_documents", [])

        applicant = self.cleaned_data.get("applicant")
        if applicant:
            application.applicant = applicant
            
            # Save dynamic fields back to applicant profile
            if commit:
                # Save application first
                application.save()
                
                # Update only the records that were displayed in the form
                from django.db import transaction
                
                with transaction.atomic():
                    # 1. Handle multiple jobs - update existing, create new, delete cleared
                    job_count = 1
                    existing_jobs = list(applicant.jobs.all().order_by('id'))
                    updated_job_ids = []
                    
                    while f'job_company_{job_count}' in self.fields:
                        company = self.cleaned_data.get(f'job_company_{job_count}')
                        position = self.cleaned_data.get(f'job_position_{job_count}')
                        income = self.cleaned_data.get(f'job_income_{job_count}')
                        
                        # Check if we have an existing job at this position
                        if job_count <= len(existing_jobs):
                            job = existing_jobs[job_count - 1]
                            if company:  # Update existing job
                                job.company_name = company
                                job.position = position or ''
                                job.annual_income = income or 0
                                job.supervisor_name = self.cleaned_data.get(f'job_supervisor_{job_count}', '')
                                job.supervisor_email = self.cleaned_data.get(f'job_supervisor_email_{job_count}', '')
                                job.supervisor_phone = self.cleaned_data.get(f'job_supervisor_phone_{job_count}', '')
                                job.currently_employed = self.cleaned_data.get(f'job_current_{job_count}', False)
                                job.employment_start_date = self.cleaned_data.get(f'job_start_date_{job_count}')
                                job.employment_end_date = self.cleaned_data.get(f'job_end_date_{job_count}')
                                job.save()
                                updated_job_ids.append(job.id)
                            else:
                                # Field was cleared - delete this job
                                job.delete()
                        else:
                            # New job entry
                            if company:
                                from applicants.models import Job
                                new_job = Job.objects.create(
                                    applicant=applicant,
                                    company_name=company,
                                    position=position or '',
                                    annual_income=income or 0,
                                    supervisor_name=self.cleaned_data.get(f'job_supervisor_{job_count}', ''),
                                    supervisor_email=self.cleaned_data.get(f'job_supervisor_email_{job_count}', ''),
                                    supervisor_phone=self.cleaned_data.get(f'job_supervisor_phone_{job_count}', ''),
                                    currently_employed=self.cleaned_data.get(f'job_current_{job_count}', False),
                                    employment_start_date=self.cleaned_data.get(f'job_start_date_{job_count}'),
                                    employment_end_date=self.cleaned_data.get(f'job_end_date_{job_count}'),
                                )
                                updated_job_ids.append(new_job.id)
                        job_count += 1
                    
                    # 2. Handle multiple income sources - same pattern
                    income_count = 1
                    existing_incomes = list(applicant.income_sources.all().order_by('id'))
                    updated_income_ids = []
                    
                    while f'income_source_{income_count}' in self.fields:
                        source_type = self.cleaned_data.get(f'income_source_{income_count}')
                        amount = self.cleaned_data.get(f'income_amount_{income_count}')
                        
                        if income_count <= len(existing_incomes):
                            income = existing_incomes[income_count - 1]
                            if source_type and amount:
                                income.income_source = source_type
                                income.average_annual_income = amount
                                income.save()
                                updated_income_ids.append(income.id)
                            else:
                                income.delete()
                        else:
                            if source_type and amount:
                                from applicants.models import IncomeSource
                                new_income = IncomeSource.objects.create(
                                    applicant=applicant,
                                    income_source=source_type,
                                    average_annual_income=amount,
                                )
                                updated_income_ids.append(new_income.id)
                        income_count += 1
                    
                    # 3. Handle multiple assets - same pattern
                    asset_count = 1
                    existing_assets = list(applicant.assets.all().order_by('id'))
                    updated_asset_ids = []
                    
                    while f'asset_name_{asset_count}' in self.fields:
                        asset_name = self.cleaned_data.get(f'asset_name_{asset_count}')
                        balance = self.cleaned_data.get(f'asset_balance_{asset_count}')
                        
                        if asset_count <= len(existing_assets):
                            asset = existing_assets[asset_count - 1]
                            if asset_name and balance:
                                asset.asset_name = asset_name
                                asset.account_balance = balance
                                asset.save()
                                updated_asset_ids.append(asset.id)
                            else:
                                asset.delete()
                        else:
                            if asset_name and balance:
                                from applicants.models import Asset
                                new_asset = Asset.objects.create(
                                    applicant=applicant,
                                    asset_name=asset_name,
                                    account_balance=balance,
                                )
                                updated_asset_ids.append(new_asset.id)
                        asset_count += 1
                    
                    # 4. Handle previous addresses - same pattern
                    address_count = 1
                    existing_addresses = list(applicant.previous_addresses.all().order_by('id'))
                    updated_address_ids = []
                    
                    while f'prev_street_address_1_{address_count}' in self.fields:
                        street1 = self.cleaned_data.get(f'prev_street_address_1_{address_count}')
                        city = self.cleaned_data.get(f'prev_city_{address_count}')
                        
                        if address_count <= len(existing_addresses):
                            address = existing_addresses[address_count - 1]
                            if street1 and city:
                                address.street_address_1 = street1
                                address.street_address_2 = self.cleaned_data.get(f'prev_street_address_2_{address_count}', '')
                                address.city = city
                                address.state = self.cleaned_data.get(f'prev_state_{address_count}', '')
                                address.zip_code = self.cleaned_data.get(f'prev_zip_code_{address_count}', '')
                                address.length_at_address = self.cleaned_data.get(f'prev_length_at_address_{address_count}', '')
                                address.housing_status = self.cleaned_data.get(f'prev_housing_status_{address_count}')
                                address.landlord_name = self.cleaned_data.get(f'prev_landlord_name_{address_count}', '')
                                address.landlord_phone = self.cleaned_data.get(f'prev_landlord_phone_{address_count}', '')
                                address.landlord_email = self.cleaned_data.get(f'prev_landlord_email_{address_count}', '')
                                address.save()
                                updated_address_ids.append(address.id)
                            else:
                                address.delete()
                        else:
                            if street1 and city:
                                from applicants.models import PreviousAddress
                                new_address = PreviousAddress.objects.create(
                                    applicant=applicant,
                                    street_address_1=street1,
                                    street_address_2=self.cleaned_data.get(f'prev_street_address_2_{address_count}', ''),
                                    city=city,
                                    state=self.cleaned_data.get(f'prev_state_{address_count}', ''),
                                    zip_code=self.cleaned_data.get(f'prev_zip_code_{address_count}', ''),
                                    length_at_address=self.cleaned_data.get(f'prev_length_at_address_{address_count}', ''),
                                    housing_status=self.cleaned_data.get(f'prev_housing_status_{address_count}'),
                                    landlord_name=self.cleaned_data.get(f'prev_landlord_name_{address_count}', ''),
                                    landlord_phone=self.cleaned_data.get(f'prev_landlord_phone_{address_count}', ''),
                                    landlord_email=self.cleaned_data.get(f'prev_landlord_email_{address_count}', ''),
                                )
                                updated_address_ids.append(new_address.id)
                        address_count += 1
                    
                    # Log activity for dynamic fields saved
                    from .models import ApplicationActivity
                    fields_saved = []
                    if updated_job_ids:
                        fields_saved.append(f"{len(updated_job_ids)} job(s)")
                    if updated_income_ids:
                        fields_saved.append(f"{len(updated_income_ids)} income source(s)")
                    if updated_asset_ids:
                        fields_saved.append(f"{len(updated_asset_ids)} asset(s)")
                    if updated_address_ids:
                        fields_saved.append(f"{len(updated_address_ids)} previous address(es)")
                    
                    if fields_saved:
                        ApplicationActivity.objects.create(
                            application=application,
                            description=f"Updated applicant profile data: {', '.join(fields_saved)}"
                        )
        else:
            # No applicant linked yet, just save the application
            if commit:
                application.save()

        return application



class ApplicantCompletionForm(forms.ModelForm):
    class Meta:
        model = Application
        fields = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})  # Style the fields

    def save(self, commit=True):
        application = super().save(commit=False)
        if commit:
            application.save()
        return application


# V2 Application System Forms

class PersonalInfoForm(forms.ModelForm):
    """Section 1 - Personal Information Form"""
    
    # Add custom field for address lookup
    address_lookup = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Start typing your address...',
            'id': 'address-lookup'
        }),
        help_text='Start typing to search for your address'
    )
    
    class Meta:
        model = PersonalInfoData
        fields = [
            'first_name', 'middle_name', 'last_name', 'suffix',
            'email', 'phone_cell', 'can_receive_sms',
            'date_of_birth', 'ssn',
            'current_address', 'apt_unit_number', 'address_duration', 'is_rental_property',
            'landlord_name', 'landlord_phone', 'landlord_email',
            'desired_address', 'desired_unit', 'desired_move_in_date',
            'referral_source', 'has_pets',
            'reference1_name', 'reference1_phone', 'reference2_name', 'reference2_phone',
            'leasing_agent',
            'has_filed_bankruptcy', 'has_criminal_conviction',
            'about_yourself'
        ]
        
        widgets = {
            # Name fields
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'suffix': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Jr., Sr., III, etc.'}),
            
            # Contact fields
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_cell': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '(555) 123-4567'
            }),
            'can_receive_sms': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            
            # Personal details
            'date_of_birth': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            'ssn': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': '123-45-6789',
                'pattern': '[0-9]{3}-[0-9]{2}-[0-9]{4}'
            }),
            
            # Address fields
            'current_address': forms.TextInput(attrs={'class': 'form-control'}),
            'apt_unit_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address_duration': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'e.g., 2 years, 6 months'
            }),
            'is_rental_property': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            
            # Landlord fields (conditional)
            'landlord_name': forms.TextInput(attrs={'class': 'form-control'}),
            'landlord_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'landlord_email': forms.EmailInput(attrs={'class': 'form-control'}),
            
            # Desired property (will be auto-filled from manual address fields if no apartment)
            'desired_address': forms.TextInput(attrs={'class': 'form-control'}),
            'desired_unit': forms.TextInput(attrs={'class': 'form-control'}),
            'desired_move_in_date': forms.DateInput(attrs={
                'class': 'form-control', 
                'type': 'date'
            }),
            
            # Additional info
            'referral_source': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'How did you hear about us?'
            }),
            'has_pets': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            
            # References
            'reference1_name': forms.TextInput(attrs={'class': 'form-control'}),
            'reference1_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'reference2_name': forms.TextInput(attrs={'class': 'form-control'}),
            'reference2_phone': forms.TextInput(attrs={'class': 'form-control'}),
            
            'leasing_agent': forms.TextInput(attrs={'class': 'form-control'}),
            
            # Legal history
            'has_filed_bankruptcy': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_criminal_conviction': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            
            'about_yourself': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 4,
                'placeholder': 'Tell us more about yourself...'
            }),
        }
        
        labels = {
            'first_name': 'First Name *',
            'middle_name': 'Middle Name',
            'last_name': 'Last Name *',
            'suffix': 'Suffix',
            'email': 'Email *',
            'phone_cell': 'Cell Phone *',
            'can_receive_sms': 'I consent to receive SMS messages',
            'date_of_birth': 'Date of Birth *',
            'ssn': 'Social Security Number *',
            'current_address': 'Current Address *',
            'apt_unit_number': 'Apt/Unit Number',
            'address_duration': 'How long have you lived at this address? *',
            'is_rental_property': 'This is a rental property',
            'landlord_name': "Landlord's Name",
            'landlord_phone': "Landlord's Phone",
            'landlord_email': "Landlord's Email",
            'desired_address': 'Desired Address *',
            'desired_unit': 'Desired Unit *',
            'desired_move_in_date': 'Move-in Date *',
            'referral_source': 'How did you hear about us? *',
            'has_pets': 'I have pets',
            'reference1_name': 'Reference #1 Name *',
            'reference1_phone': 'Reference #1 Phone *',
            'reference2_name': 'Reference #2 Name',
            'reference2_phone': 'Reference #2 Phone',
            'leasing_agent': 'Leasing Agent',
            'has_filed_bankruptcy': 'I have filed for bankruptcy',
            'has_criminal_conviction': 'I have a criminal conviction',
            'about_yourself': 'Tell us more about yourself',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make landlord fields conditional
        landlord_fields = ['landlord_name', 'landlord_phone', 'landlord_email']
        for field in landlord_fields:
            self.fields[field].widget.attrs['data-conditional'] = 'is_rental_property'
    
    def clean_ssn(self):
        """Validate and format SSN"""
        ssn = self.cleaned_data.get('ssn')
        if ssn:
            # Remove any non-digits
            ssn_digits = ''.join(filter(str.isdigit, ssn))
            
            # Validate length
            if len(ssn_digits) != 9:
                raise forms.ValidationError("SSN must be 9 digits long")
            
            # Format as XXX-XX-XXXX
            formatted_ssn = f"{ssn_digits[:3]}-{ssn_digits[3:5]}-{ssn_digits[5:]}"
            return formatted_ssn
        
        return ssn
    
    def clean_phone_cell(self):
        """Validate and format phone number"""
        phone = self.cleaned_data.get('phone_cell')
        if phone:
            # Remove any non-digits
            phone_digits = ''.join(filter(str.isdigit, phone))
            
            # Validate length
            if len(phone_digits) != 10:
                raise forms.ValidationError("Phone number must be 10 digits long")
            
            # Format as (XXX) XXX-XXXX
            formatted_phone = f"({phone_digits[:3]}) {phone_digits[3:6]}-{phone_digits[6:]}"
            return formatted_phone
        
        return phone
    
    def clean(self):
        cleaned_data = super().clean()
        is_rental = cleaned_data.get('is_rental_property')
        
        # If it's a rental property, landlord fields are required
        if is_rental:
            required_fields = ['landlord_name', 'landlord_phone']
            for field in required_fields:
                if not cleaned_data.get(field):
                    self.add_error(field, f"This field is required when current address is a rental property")
        
        return cleaned_data


class PreviousAddressForm(forms.ModelForm):
    """Form for adding previous addresses"""
    
    class Meta:
        model = PreviousAddress
        fields = ['address', 'apt_unit', 'duration', 'landlord_name', 'landlord_contact']
        
        widgets = {
            'address': forms.TextInput(attrs={'class': 'form-control', 'required': True}),
            'apt_unit': forms.TextInput(attrs={'class': 'form-control'}),
            'duration': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'e.g., 1 year, 6 months',
                'required': True
            }),
            'landlord_name': forms.TextInput(attrs={'class': 'form-control'}),
            'landlord_contact': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Phone or email'
            }),
        }
        
        labels = {
            'address': 'Previous Address *',
            'apt_unit': 'Apt/Unit Number',
            'duration': 'How long did you live there? *',
            'landlord_name': "Previous Landlord's Name",
            'landlord_contact': "Previous Landlord's Contact",
        }


class IncomeForm(forms.ModelForm):
    """Section 2 - Income & Employment Form"""
    
    class Meta:
        model = IncomeData
        fields = [
            'employment_type', 'company_name', 'position', 'annual_income',
            'supervisor_name', 'supervisor_phone', 'supervisor_email',
            'currently_employed', 'start_date', 'end_date',
            'has_multiple_jobs', 'has_additional_income', 'has_assets'
        ]
        
        widgets = {
            'employment_type': forms.Select(attrs={'class': 'form-select'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'annual_income': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'supervisor_name': forms.TextInput(attrs={'class': 'form-control'}),
            'supervisor_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '(555) 123-4567'}),
            'supervisor_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'currently_employed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'has_multiple_jobs': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_additional_income': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_assets': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Make most fields optional except key employment fields
        required_fields = ['employment_type', 'company_name', 'position', 'annual_income', 'start_date']
        for field_name, field in self.fields.items():
            field.required = field_name in required_fields


