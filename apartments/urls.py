from django.urls import path, include
from . import views

urlpatterns = [
    path('', views.apartments_list, name='apartments_list'),
    path('<int:apartment_id>/edit/', views.apartment_edit, name='apartment_edit'),
    path('<int:apartment_id>/overview/', views.apartment_overview, name='apartment_overview'),
    path('<int:apartment_id>/contact-broker/', views.contact_broker, name='contact_broker'),
    path("get-apartment-data/<int:apartment_id>/", views.get_apartment_data, name="get_apartment_data"),
    
    # Multi-step apartment creation
    path('create-v2/', views.create_apartment_v2, name='create_apartment_v2'),
    path('create-v2/<int:building_id>/', views.create_apartment_v2, name='create_apartment_v2_with_building'),
    path('<int:apartment_id>/step2/', views.apartment_step2, name='apartment_step2'),
    path('<int:apartment_id>/step3/', views.apartment_step3, name='apartment_step3'),
    path('<int:apartment_id>/step4/', views.apartment_step4, name='apartment_step4'),
    path('<int:apartment_id>/complete/', views.apartment_complete, name='apartment_complete'),
    
    # API endpoints
    path('api/', include('apartments.api_urls')),
]
