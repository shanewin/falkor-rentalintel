from django.contrib import admin
from .models import Applicant

class ApplicantAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'phone_number')  # FIXED

admin.site.register(Applicant, ApplicantAdmin)
