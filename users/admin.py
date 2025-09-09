from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

class UserAdmin(BaseUserAdmin):
    list_display = ("email", "is_staff", "is_active", "is_superuser", "is_broker", "is_applicant", "is_owner", "created_at")
    list_filter = ("is_staff", "is_superuser", "is_active", "is_broker", "is_applicant", "is_owner")
    
    # 🚀 Ensure clear separation of roles & permissions
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser")}),  # ✅ Keep superuser separate
        ("User Roles", {"fields": ("is_broker", "is_applicant", "is_owner")}),  # ✅ Ensure owners don't get admin access
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    # 🚀 Improve Add User Form to Ensure Proper Role Assignments
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2", "is_staff", "is_superuser", "is_broker", "is_applicant", "is_owner"),
        }),
    )
    
    search_fields = ("email",)
    ordering = ("email",)
    readonly_fields = ("created_at", "updated_at")  # ✅ Make timestamps read-only

admin.site.register(User, UserAdmin)
