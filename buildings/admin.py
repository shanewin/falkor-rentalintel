from django.contrib import admin
from .models import Building, Amenity, BuildingImage, BuildingAccess, BuildingSpecial


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


@admin.register(Building)
class BuildingAdmin(admin.ModelAdmin):
    list_display = ('name', 'street_address_1', 'city', 'state', 'zip_code', 'neighborhood', 'get_broker_count')
    search_fields = ('name', 'street_address_1', 'city', 'state', 'zip_code', 'neighborhood')
    list_filter = ('state', 'amenities', 'pet_policy', 'commission_pay_type')
    inlines = [BuildingImageInline, BuildingAccessInline, BuildingSpecialInline]
    filter_horizontal = ('amenities', 'brokers')  # ADD BROKERS to enable assignment
    
    def get_broker_count(self, obj):
        """Display number of brokers assigned to this building"""
        return obj.brokers.count()
    get_broker_count.short_description = 'Assigned Brokers'


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

