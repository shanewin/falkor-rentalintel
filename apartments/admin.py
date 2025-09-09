from django.contrib import admin
from .models import Apartment, ApartmentImage

@admin.register(Apartment)
class ApartmentAdmin(admin.ModelAdmin):
    list_display = ('building', 'unit_number', 'bedrooms', 'bathrooms', 'rent_price', 'status')

@admin.register(ApartmentImage)
class ApartmentImageAdmin(admin.ModelAdmin):
    list_display = ('apartment', 'image')
