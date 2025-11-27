"""
Admin configuration for apartments app.
Business Context: Provides administrative interface for managing rental inventory,
pricing, availability, and property features.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import (
    Apartment, ApartmentAmenity, ApartmentImage, ApartmentConcession
)
from .models_extended import (
    ApartmentAvailability, ApartmentPriceHistory, ApartmentVirtualTour,
    ApartmentFloorPlan, ApartmentUtilities, ApartmentParking
)


# Inline admins for related models
class ApartmentImageInline(admin.TabularInline):
    model = ApartmentImage
    extra = 1
    fields = ['image', 'thumbnail_preview']
    readonly_fields = ['thumbnail_preview']
    
    def thumbnail_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" />', obj.thumbnail_url())
        return "No image"
    thumbnail_preview.short_description = "Preview"


class ApartmentConcessionInline(admin.TabularInline):
    model = ApartmentConcession
    extra = 0
    fields = ['name', 'months_free', 'lease_terms', 'special_offer_id']


class ApartmentAvailabilityInline(admin.StackedInline):
    model = ApartmentAvailability
    extra = 0
    fields = [
        ('available_date', 'current_lease_end'),
        ('is_reserved', 'reserved_until', 'reserved_by'),
        'turnover_days',
        'notes'
    ]


class ApartmentPriceHistoryInline(admin.TabularInline):
    model = ApartmentPriceHistory
    extra = 0
    fields = ['effective_date', 'rent_price', 'net_effective_rent', 'change_reason', 'end_date']
    readonly_fields = ['created_at']
    ordering = ['-effective_date']


class ApartmentVirtualTourInline(admin.TabularInline):
    model = ApartmentVirtualTour
    extra = 0
    fields = ['tour_type', 'tour_url', 'title', 'is_active', 'view_count']
    readonly_fields = ['view_count']


class ApartmentParkingInline(admin.TabularInline):
    model = ApartmentParking
    extra = 0
    fields = ['parking_type', 'spaces_included', 'spaces_available', 'monthly_rate', 'has_ev_charging']


@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    """
    Main apartment admin interface.
    Business Impact: Enables efficient management of rental inventory.
    """
    list_display = [
        'unit_number', 
        'building_link', 
        'bedrooms', 
        'bathrooms',
        'square_feet',
        'rent_price_display',
        'status_badge',
        'availability_status',
        'last_modified'
    ]
    
    list_filter = [
        'status',
        'apartment_type',
        'building__neighborhood',
        'bedrooms',
        'broker_fee_required',
        'last_modified'
    ]
    
    search_fields = [
        'unit_number',
        'building__name',
        'building__street_address_1',
        'description'
    ]
    
    readonly_fields = ['last_modified', 'get_filled_fields_display']
    
    fieldsets = [
        ('Basic Information', {
            'fields': [
                'building',
                ('unit_number', 'apartment_type'),
                ('bedrooms', 'bathrooms', 'square_feet'),
                'status'
            ]
        }),
        ('Pricing', {
            'fields': [
                ('rent_price', 'net_price'),
                ('deposit_price', 'holding_deposit'),
                'broker_fee_required'
            ]
        }),
        ('Details', {
            'fields': [
                'description',
                'amenities',
                'lock_type',
                'lease_duration',
                'paid_months',
                'free_stuff',
                'required_documents'
            ]
        }),
        ('System Information', {
            'fields': ['last_modified', 'get_filled_fields_display'],
            'classes': ['collapse']
        })
    ]
    
    inlines = [
        ApartmentAvailabilityInline,
        ApartmentPriceHistoryInline,
        ApartmentImageInline,
        ApartmentConcessionInline,
        ApartmentVirtualTourInline,
        ApartmentParkingInline,
    ]
    
    filter_horizontal = ['amenities']
    
    def building_link(self, obj):
        """Link to building admin"""
        url = reverse('admin:buildings_building_change', args=[obj.building.id])
        return format_html('<a href="{}">{}</a>', url, obj.building.name)
    building_link.short_description = "Building"
    building_link.admin_order_field = "building__name"
    
    def rent_price_display(self, obj):
        """Format rent price with currency"""
        if obj.net_price and obj.net_price < obj.rent_price:
            return format_html(
                '<s>${:,.0f}</s><br/><b>${:,.0f}</b>',
                obj.rent_price,
                obj.net_price
            )
        return f"${obj.rent_price:,.0f}"
    rent_price_display.short_description = "Rent"
    rent_price_display.admin_order_field = "rent_price"
    
    def status_badge(self, obj):
        """Color-coded status badge"""
        colors = {
            'available': 'green',
            'pending': 'orange',
            'rented': 'red',
            'unavailable': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"
    
    def availability_status(self, obj):
        """Show availability date if set"""
        availability = obj.get_current_availability()
        if availability:
            if availability.is_reserved:
                return format_html(
                    '<span style="color: orange;">Reserved until {}</span>',
                    availability.reserved_until
                )
            elif availability.available_date > timezone.now().date():
                return format_html(
                    '<span style="color: blue;">Available {}</span>',
                    availability.available_date
                )
            else:
                return format_html(
                    '<span style="color: green;">Available Now</span>'
                )
        return "-"
    availability_status.short_description = "Availability"
    
    def get_filled_fields_display(self, obj):
        """Display filled fields in admin"""
        fields = obj.get_filled_fields()
        items = [f"<li><b>{k}:</b> {v}</li>" for k, v in fields.items()]
        return format_html("<ul>{}</ul>", "".join(items))
    get_filled_fields_display.short_description = "Filled Fields"


@admin.register(ApartmentAmenity)
class ApartmentAmenityAdmin(admin.ModelAdmin):
    """Manage apartment-specific amenities"""
    list_display = ['name', 'apartment_count']
    search_fields = ['name']
    ordering = ['name']
    
    def apartment_count(self, obj):
        """Count of apartments with this amenity"""
        return obj.apartment_set.count()
    apartment_count.short_description = "# Apartments"


@admin.register(ApartmentImage)
class ApartmentImageAdmin(admin.ModelAdmin):
    """Manage apartment images"""
    list_display = ['apartment', 'image', 'thumbnail_preview']
    list_filter = ['apartment__building']
    search_fields = ['apartment__unit_number', 'apartment__building__name']
    readonly_fields = ['thumbnail_preview', 'large_preview']
    
    def thumbnail_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" />', obj.thumbnail_url())
        return "No image"
    thumbnail_preview.short_description = "Thumbnail"
    
    def large_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="400" />', obj.large_url())
        return "No image"
    large_preview.short_description = "Large Preview"


@admin.register(ApartmentAvailability)
class ApartmentAvailabilityAdmin(admin.ModelAdmin):
    """Manage apartment availability calendar"""
    list_display = [
        'apartment',
        'available_date',
        'current_lease_end',
        'is_reserved',
        'reserved_until',
        'turnover_days'
    ]
    list_filter = [
        'is_reserved',
        'available_date',
        'apartment__building'
    ]
    search_fields = [
        'apartment__unit_number',
        'apartment__building__name',
        'reserved_by'
    ]
    date_hierarchy = 'available_date'
    

@admin.register(ApartmentPriceHistory)
class ApartmentPriceHistoryAdmin(admin.ModelAdmin):
    """Track pricing changes over time"""
    list_display = [
        'apartment',
        'rent_price',
        'net_effective_rent',
        'effective_date',
        'end_date',
        'change_reason',
        'is_current'
    ]
    list_filter = [
        'change_reason',
        'effective_date',
        'apartment__building'
    ]
    search_fields = [
        'apartment__unit_number',
        'apartment__building__name'
    ]
    date_hierarchy = 'effective_date'
    
    def is_current(self, obj):
        """Check if this is the current price"""
        return obj.end_date is None
    is_current.boolean = True
    is_current.short_description = "Current"


@admin.register(ApartmentVirtualTour)
class ApartmentVirtualTourAdmin(admin.ModelAdmin):
    """Manage virtual tours"""
    list_display = [
        'apartment',
        'tour_type',
        'title',
        'is_active',
        'view_count',
        'created_at'
    ]
    list_filter = [
        'tour_type',
        'is_active',
        'apartment__building'
    ]
    search_fields = [
        'apartment__unit_number',
        'apartment__building__name',
        'title'
    ]
    readonly_fields = ['view_count', 'created_at', 'updated_at']


@admin.register(ApartmentFloorPlan)
class ApartmentFloorPlanAdmin(admin.ModelAdmin):
    """Manage floor plans"""
    list_display = [
        'apartment',
        'title',
        'total_square_feet',
        'is_primary',
        'is_active',
        'display_order'
    ]
    list_filter = [
        'is_primary',
        'is_active',
        'apartment__building'
    ]
    search_fields = [
        'apartment__unit_number',
        'apartment__building__name',
        'title'
    ]
    ordering = ['display_order', 'apartment']


@admin.register(ApartmentUtilities)
class ApartmentUtilitiesAdmin(admin.ModelAdmin):
    """Manage utilities information"""
    list_display = [
        'apartment',
        'utilities_included_count',
        'estimated_included_value',
        'updated_at'
    ]
    search_fields = [
        'apartment__unit_number',
        'apartment__building__name'
    ]
    fieldsets = [
        ('Apartment', {
            'fields': ['apartment']
        }),
        ('Included in Rent', {
            'fields': [
                ('water_included', 'gas_included', 'electricity_included'),
                ('heat_included', 'hot_water_included'),
                ('trash_included', 'sewer_included'),
                ('internet_included', 'cable_included')
            ]
        }),
        ('Cost Estimates (if not included)', {
            'fields': [
                ('water_cost_estimate', 'gas_cost_estimate', 'electricity_cost_estimate')
            ]
        }),
        ('Utility Providers', {
            'fields': [
                'electricity_provider',
                'gas_provider',
                'internet_providers'
            ]
        }),
        ('Metering', {
            'fields': [
                ('electricity_meter_type', 'gas_meter_type', 'water_meter_type')
            ]
        }),
        ('Additional Information', {
            'fields': ['utility_notes']
        })
    ]
    
    def utilities_included_count(self, obj):
        """Count of included utilities"""
        return len(obj.get_included_utilities_list())
    utilities_included_count.short_description = "# Included"
    
    def estimated_included_value(self, obj):
        """Total value of included utilities"""
        value = obj.get_total_included_value()
        return f"${value:.0f}/mo" if value else "-"
    estimated_included_value.short_description = "Est. Value"


@admin.register(ApartmentParking)
class ApartmentParkingAdmin(admin.ModelAdmin):
    """Manage parking options"""
    list_display = [
        'apartment',
        'parking_type',
        'spaces_included',
        'spaces_available',
        'monthly_rate',
        'has_ev_charging'
    ]
    list_filter = [
        'parking_type',
        'has_ev_charging',
        'is_assigned',
        'apartment__building'
    ]
    search_fields = [
        'apartment__unit_number',
        'apartment__building__name'
    ]
    fieldsets = [
        ('Basic Information', {
            'fields': [
                'apartment',
                'parking_type',
                ('spaces_included', 'spaces_available'),
                'monthly_rate'
            ]
        }),
        ('Location', {
            'fields': [
                'location_description',
                'distance_from_unit',
                ('height_clearance', 'compact_only')
            ]
        }),
        ('Features', {
            'fields': [
                'is_assigned',
                ('has_ev_charging', 'ev_charging_cost'),
                'access_type'
            ]
        }),
        ('Guest Parking', {
            'fields': [
                'guest_parking_available',
                'guest_parking_details'
            ]
        }),
        ('Additional', {
            'fields': [
                'waitlist_available',
                'notes'
            ]
        })
    ]


@admin.register(ApartmentConcession)
class ApartmentConcessionAdmin(admin.ModelAdmin):
    """Manage rental concessions and incentives"""
    list_display = [
        'apartment',
        'name',
        'months_free',
        'lease_terms',
        'special_offer_id'
    ]
    list_filter = [
        'apartment__building',
        'months_free'
    ]
    search_fields = [
        'apartment__unit_number',
        'apartment__building__name',
        'name'
    ]