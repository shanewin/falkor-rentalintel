from django.urls import path
from . import views


urlpatterns = [
    path('', views.buildings_list, name='buildings_list'), 
    path('create/', views.create_building, name='create_building'),
    path('<int:building_id>/', views.building_detail, name='building_detail'),
    path('<int:building_id>/overview/', views.building_overview, name='building_overview'),
    
    # Multi-step building creation
    path('<int:building_id>/step2/', views.building_step2, name='building_step2'),
    path('<int:building_id>/step3/', views.building_step3, name='building_step3'),
    path('<int:building_id>/step4/', views.building_step4, name='building_step4'),
    path('<int:building_id>/complete/', views.building_complete, name='building_complete'),

]
