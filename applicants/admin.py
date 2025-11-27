from django.contrib import admin
from .models import Applicant, ApplicantActivity, ApplicantCRM

class ApplicantAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phone_number', 'assigned_broker', 'placement_status')
    list_filter = ('placement_status', 'assigned_broker', 'currently_employed')  # FIX: removed non-existent field
    search_fields = ('first_name', 'last_name', 'email', 'phone_number')
    raw_id_fields = ('user', 'assigned_broker')  # Use popup selector for user fields
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'first_name', 'last_name', 'email', 'phone_number')
        }),
        ('Broker Assignment', {
            'fields': ('assigned_broker', 'placement_status'),
            'description': 'Assign a broker to manage this applicant'
        }),
        ('Employment Status', {
            'fields': ('currently_employed', 'employment_status', 'company_name')  # FIX: use existing fields
        }),
    )
    
    def get_broker_name(self, obj):
        """Display broker's email or name"""
        if obj.assigned_broker:
            return obj.assigned_broker.email
        return '-'
    get_broker_name.short_description = 'Assigned Broker'

class ApplicantActivityAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'activity_type', 'created_at', 'triggered_by')
    list_filter = ('activity_type', 'created_at')
    search_fields = ('applicant__first_name', 'applicant__last_name', 'description')
    readonly_fields = ('created_at',)

class ApplicantCRMAdmin(admin.ModelAdmin):
    list_display = ('applicant', 'assigned_broker', 'status', 'last_updated')
    list_filter = ('status', 'assigned_broker')
    search_fields = ('applicant__first_name', 'applicant__last_name', 'applicant__email')
    raw_id_fields = ('applicant', 'assigned_broker')

admin.site.register(Applicant, ApplicantAdmin)
admin.site.register(ApplicantActivity, ApplicantActivityAdmin)
admin.site.register(ApplicantCRM, ApplicantCRMAdmin)
