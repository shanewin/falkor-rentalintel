from django.contrib import admin
from .models import Building, Amenity, BuildingImage, BuildingAccess, BuildingSpecial, NearbySchool
from .neighborhood_service import NeighborhoodService
from django.contrib import messages


class BuildingImageInline(admin.TabularInline):
    model = BuildingImage
    extra = 1


class BuildingAccessInline(admin.TabularInline):
    model = BuildingAccess
    extra = 1
    fields = ('location', 'time_restriction_enabled', 'access_type', 'pin_code', 'custom_note', 'image')
    # Optional: Customize readonly fields or fieldsets later if needed


class BuildingSpecialInline(admin.TabularInline):
    model = BuildingSpecial
    extra = 1
    fields = (
        'special_type', 'name', 'months_free', 'lease_terms', 'additional_info', 'free_stuff_items',
        'is_time_based', 'date_from', 'date_to', 'trigger_event',
    )
    # Optional: You could customize the form later to conditionally show fields


class NearbySchoolInline(admin.TabularInline):
    model = NearbySchool
    extra = 0
    readonly_fields = ('name', 'rating', 'grades', 'distance', 'school_type')


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ('name', 'street_address_1', 'city', 'state', 'zip_code', 'neighborhood', 'get_broker_count')
    search_fields = ('name', 'street_address_1', 'city', 'state', 'zip_code', 'neighborhood')
    list_filter = ('state', 'amenities', 'pet_policy', 'commission_pay_type')
    inlines = [BuildingImageInline, BuildingAccessInline, BuildingSpecialInline, NearbySchoolInline]
    actions = ['refresh_neighborhood_data']
    
    fieldsets = (
        (None, {
            'fields': ('name', 'street_address_1', 'street_address_2', 'city', 'state', 'zip_code', 'neighborhood')
        }),
        ('Coordinates (Required for Discovery)', {
            'fields': ('latitude', 'longitude'),
            'description': 'Latitude and Longitude are required for the "Neighborhood" and "Maps" features to work.'
        }),
        ('Neighborhood Scores (Cached)', {
            'fields': (('walk_score', 'walk_description'), ('bike_score', 'bike_description'), ('transit_score', 'transit_description'), 'neighborhood_data_updated'),
            'classes': ('collapse',),
        }),
        ('Financials & Policy', {
            'fields': (('credit_screening_fee', 'credit_screening_payment_method'), ('hold_deposit', 'hold_deposit_payment_method'), 'pet_policy')
        }),
        ('Marketing & Description', {
            'fields': ('description', 'amenities', 'brokers', 'owner_name', 'company_name')
        }),
        ('Internal Notes', {
            'fields': ('internal_notes',),
            'classes': ('collapse',),
        }),
    )
    filter_horizontal = ('amenities', 'brokers')  # ADD BROKERS to enable assignment
    
    def get_broker_count(self, obj):
        """Display number of brokers assigned to this building"""
        return obj.brokers.count()
    get_broker_count.short_description = 'Assigned Brokers'

    def refresh_neighborhood_data(self, request, queryset):
        """Action to manually trigger an update of Walk Score and School data."""
        success_count = 0
        for building in queryset:
            if NeighborhoodService.update_building_data(building.id):
                success_count += 1
        
        if success_count:
            self.message_user(request, f"Successfully updated neighborhood data for {success_count} buildings.", messages.SUCCESS)
        if success_count < queryset.count():
            self.message_user(request, f"Failed to update data for {queryset.count() - success_count} buildings. Check coordinates.", messages.ERROR)
    
    refresh_neighborhood_data.short_description = "Refresh Neighborhood Data (Walk Score/Schools)"


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

