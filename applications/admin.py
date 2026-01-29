from django.contrib import admin
from .models import (
    Application, UploadedFile, ApplicationActivity, ApplicationSection,
    PersonalInfoData, PreviousAddress, IncomeData, AdditionalEmployment,
    AdditionalIncome, AssetInfo, LegalDocuments, ApplicationPayment
)

# Existing admin classes
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'applicant', 'apartment', 'broker', 'status', 'application_version', 'submitted_by_applicant')
    list_filter = ('status', 'application_version', 'submitted_by_applicant', 'broker')
    search_fields = ('applicant__first_name', 'applicant__last_name', 'applicant__email')
    readonly_fields = ('unique_link', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('applicant', 'apartment', 'broker', 'status')
        }),
        ('Application Details', {
            'fields': ('submitted_by_applicant', 'required_documents', 'unique_link')
        }),
        ('V2 System Fields', {
            'fields': ('application_version', 'current_section', 'section_statuses', 'application_fee_amount')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )

class UploadedFileAdmin(admin.ModelAdmin):
    list_display = ('application', 'document_type', 'uploaded_at', 'short_analysis_results')
    list_filter = ('document_type',)
    readonly_fields = ('analysis_results',)
    search_fields = ('application__applicant__first_name', 'application__applicant__last_name')

    def short_analysis_results(self, obj):
        """Show a short preview of analysis results in the admin panel."""
        return (obj.analysis_results[:75] + '...') if obj.analysis_results else "No analysis yet"
    
    short_analysis_results.short_description = "Analysis Summary"

# New V2 admin classes
class ApplicationActivityAdmin(admin.ModelAdmin):
    list_display = ('application', 'description', 'timestamp')
    list_filter = ('timestamp',)
    search_fields = ('application__id', 'description')
    readonly_fields = ('timestamp',)

class ApplicationSectionAdmin(admin.ModelAdmin):
    list_display = ('application', 'section_number', 'status', 'is_valid', 'last_modified')
    list_filter = ('section_number', 'status', 'is_valid')
    search_fields = ('application__id',)
    readonly_fields = ('last_modified',)

class PreviousAddressInline(admin.TabularInline):
    model = PreviousAddress
    extra = 0

class PersonalInfoDataAdmin(admin.ModelAdmin):
    list_display = ('application', 'first_name', 'last_name', 'email', 'phone_cell', 'has_pets')
    list_filter = ('is_rental_property', 'has_pets', 'has_filed_bankruptcy', 'has_criminal_conviction')
    search_fields = ('first_name', 'last_name', 'email', 'phone_cell')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [PreviousAddressInline]
    
    fieldsets = (
        ('Name', {
            'fields': ('first_name', 'middle_name', 'last_name', 'suffix')
        }),
        ('Contact Information', {
            'fields': ('email', 'phone_cell')
        }),
        ('Personal Details', {
            'fields': ('date_of_birth', 'ssn')
        }),
        ('Current Address', {
            'fields': ('street_address_1', 'street_address_2', 'city', 'state', 'zip_code', 'current_address_years', 'current_address_months', 'is_rental_property')
        }),
        ('Landlord Info', {
            'fields': ('landlord_name', 'landlord_phone', 'landlord_email'),
            'classes': ('collapse',)
        }),
        ('Desired Property', {
            'fields': ('desired_address', 'desired_unit', 'desired_move_in_date')
        }),
        ('References', {
            'fields': ('reference1_name', 'reference1_phone', 'reference2_name', 'reference2_phone')
        }),
        ('Additional Info', {
            'fields': ('referral_source', 'has_pets', 'has_filed_bankruptcy', 
                      'has_criminal_conviction')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

class AdditionalEmploymentInline(admin.TabularInline):
    model = AdditionalEmployment
    extra = 0

class AdditionalIncomeInline(admin.TabularInline):
    model = AdditionalIncome
    extra = 0

class AssetInfoInline(admin.TabularInline):
    model = AssetInfo
    extra = 0

class IncomeDataAdmin(admin.ModelAdmin):
    list_display = ('application', 'employment_type', 'employer', 'job_title', 'annual_income')
    list_filter = ('employment_type', 'currently_employed', 'has_multiple_jobs')
    search_fields = ('employer', 'job_title')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [AdditionalEmploymentInline, AdditionalIncomeInline, AssetInfoInline]
    
    fieldsets = (
        ('Employment Type', {
            'fields': ('employment_type',)
        }),
        ('Primary Employment', {
            'fields': ('employer', 'job_title', 'annual_income', 'employment_length', 'supervisor_name', 
                      'supervisor_email', 'supervisor_phone', 'currently_employed', 'start_date', 'end_date')
        }),
        ('Additional Income Flags', {
            'fields': ('has_multiple_jobs', 'has_additional_income', 'has_assets')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

class LegalDocumentsAdmin(admin.ModelAdmin):
    list_display = ('application', 'discrimination_form_signed', 'brokers_form_signed', 'updated_at')
    list_filter = ('discrimination_form_signed', 'brokers_form_signed')
    readonly_fields = ('discrimination_form_signed_at', 'discrimination_form_ip', 
                      'brokers_form_signed_at', 'brokers_form_ip', 'created_at', 'updated_at')
    
    fieldsets = (
        ('NY Discrimination Form', {
            'fields': ('discrimination_form_viewed', 'discrimination_form_signed', 
                      'discrimination_form_signature', 'discrimination_form_signed_at', 
                      'discrimination_form_ip')
        }),
        ('NY Brokers Form', {
            'fields': ('brokers_form_viewed', 'brokers_form_signed', 
                      'brokers_form_signature', 'brokers_form_signed_at', 
                      'brokers_form_ip')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

class ApplicationPaymentAdmin(admin.ModelAdmin):
    list_display = ('application', 'amount', 'status', 'payment_method', 'paid_at')
    list_filter = ('status', 'payment_method')
    search_fields = ('application__id', 'payment_intent_id', 'transaction_id')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Payment Information', {
            'fields': ('amount', 'status')
        }),
        ('Transaction Details', {
            'fields': ('payment_intent_id', 'payment_method', 'transaction_id', 
                      'paid_at', 'receipt_url')
        }),
        ('Refund Information', {
            'fields': ('refunded_at', 'refund_reason', 'refund_amount'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

# Register all models
admin.site.register(Application, ApplicationAdmin)
admin.site.register(UploadedFile, UploadedFileAdmin)
admin.site.register(ApplicationActivity, ApplicationActivityAdmin)
admin.site.register(ApplicationSection, ApplicationSectionAdmin)
admin.site.register(PersonalInfoData, PersonalInfoDataAdmin)
admin.site.register(IncomeData, IncomeDataAdmin)
admin.site.register(LegalDocuments, LegalDocumentsAdmin)
admin.site.register(ApplicationPayment, ApplicationPaymentAdmin)

