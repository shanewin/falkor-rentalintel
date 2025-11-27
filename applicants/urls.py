from django.urls import path, include
from .views import delete_applicant_photo, delete_pet_photo, applicant_overview, applicants_list, applicant_crm, get_applicant_data
from .profile_views import progressive_profile, quick_profile_update, profile_step1, profile_step2, profile_step3
from .activity_views import activity_dashboard, activity_timeline, activity_analytics_api

urlpatterns = [
    path('profile/<int:applicant_id>/', applicant_overview, name='applicant_overview'),
    path('delete-photo/<int:photo_id>/', delete_applicant_photo, name='delete_applicant_photo'),
    path('delete-pet-photo/<int:photo_id>/', delete_pet_photo, name='delete_pet_photo'),
    path("applicants/", applicants_list, name="applicants_list"),
    path("<int:applicant_id>/crm/", applicant_crm, name="applicant_crm"),
    path("get-applicant-data/<int:applicant_id>/", get_applicant_data, name="get_applicant_data"),
    
    # Progressive profile system
    path('my-profile/', progressive_profile, name='progressive_profile'),
    path('my-profile/quick/', quick_profile_update, name='quick_profile_update'),
    
    # Multi-step profile system
    path('my-profile/step1/', profile_step1, name='profile_step1'),
    path('my-profile/step2/', profile_step2, name='profile_step2'),
    path('my-profile/step3/', profile_step3, name='profile_step3'),
    
    # Activity tracking dashboard
    path('activity/dashboard/', activity_dashboard, name='activity_dashboard'),
    path('activity/timeline/<int:applicant_id>/', activity_timeline, name='activity_timeline'),
    path('api/activity/analytics/', activity_analytics_api, name='activity_analytics_api'),
]
