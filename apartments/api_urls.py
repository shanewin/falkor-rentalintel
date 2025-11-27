"""
API URL configuration for apartments app.
Business Context: RESTful endpoints for programmatic access to apartment inventory.
"""

from django.urls import path
from . import api_views
from . import search_api

# Note: app_name removed to avoid namespace conflicts
# URLs will be accessed directly without namespace prefix

urlpatterns = [
    # Apartment endpoints
    path('apartments/', api_views.apartment_list_api, name='apartment_list'),
    path('apartments/<int:apartment_id>/', api_views.apartment_detail_api, name='apartment_detail'),
    path('apartments/<int:apartment_id>/status/', api_views.update_apartment_status_api, name='update_status'),
    path('apartments/search/', api_views.apartment_search_api, name='apartment_search'),
    
    # Advanced search endpoints
    path('apartments/search/advanced/', search_api.search_apartments_api, name='advanced_search'),
    path('apartments/search/suggestions/', search_api.search_suggestions_api, name='search_suggestions'),
    path('apartments/search/click/', search_api.record_search_click_api, name='record_click'),
    path('apartments/search/rebuild-index/', search_api.rebuild_search_index_api, name='rebuild_index'),
    
    # Saved searches
    path('apartments/searches/saved/', search_api.saved_searches_api, name='saved_searches'),
    path('apartments/searches/saved/<int:search_id>/use/', search_api.use_saved_search_api, name='use_saved_search'),
    path('apartments/searches/popular/', search_api.popular_searches_api, name='popular_searches'),
    
    # Building endpoints
    path('buildings/<int:building_id>/apartments/', api_views.building_apartments_api, name='building_apartments'),
    
    # Reference data endpoints
    path('amenities/', api_views.apartment_amenities_api, name='amenities'),
    path('neighborhoods/', api_views.neighborhoods_api, name='neighborhoods'),
]