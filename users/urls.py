from django.urls import path, include
from . import views
from . import profile_views
from . import sms_views
from . import email_views

urlpatterns = [
    # Authentication
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Registration
    path('register/broker/', views.register_broker, name='register_broker'),
    path('register/applicant/', views.register_applicant, name='register_applicant'),
    path('register/staff/', views.register_staff, name='register_staff'),
    path('register/owner/', views.register_owner, name='register_owner'),
    
    # Secure token-based account setup
    path('set-password/<str:uidb64>/<str:token>/', views.set_password_view, name='set_password'),
    path('activate/<str:uidb64>/<str:token>/', views.activate_account_view, name='activate_account'),
    
    # Dashboards
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/staff/', views.staff_dashboard, name='staff_dashboard'),
    path('dashboard/broker/', views.broker_dashboard, name='broker_dashboard'),
    path('dashboard/applicant/', views.applicant_dashboard, name='applicant_dashboard'),
    path('dashboard/owner/', views.owner_dashboard, name='owner_dashboard'),
    
    # Admin user management
    path('admin/users/', views.admin_user_management, name='admin_user_management'),
    path('admin/create/<str:account_type>/', views.admin_create_account, name='admin_create_account'),
    path('admin/broker-leaderboard/', views.broker_leaderboard, name='broker_leaderboard'),
    
    # Profile management
    path('profile/admin/', profile_views.admin_progressive_profile, name='admin_progressive_profile'),
    path('profile/admin/quick/', profile_views.quick_admin_profile_update, name='quick_admin_profile_update'),
    path('profile/broker/', profile_views.broker_progressive_profile, name='broker_progressive_profile'),
    path('profile/broker/quick/', profile_views.quick_broker_profile_update, name='quick_broker_profile_update'),
    path('profile/owner/', profile_views.owner_progressive_profile, name='owner_progressive_profile'),
    path('profile/owner/quick/', profile_views.quick_owner_profile_update, name='quick_owner_profile_update'),
    path('profile/staff/', profile_views.staff_progressive_profile, name='staff_progressive_profile'),
    path('profile/staff/quick/', profile_views.quick_staff_profile_update, name='quick_staff_profile_update'),
    
    # Django built-in auth views (password change, reset, etc.)
    path('', include('django.contrib.auth.urls')),
    
    # Email Verification (Primary - Required)
    path('verify-email/<str:email>/', email_views.email_verification_view, name='email_verification'),
    path('verify-email/', email_views.email_verification_view, name='email_verification_no_param'),
    path('resend-email-verification/', email_views.resend_email_verification_view, name='resend_email_verification'),
    
    # SMS Verification and Preferences (Secondary - Optional)
    path('verify-phone/<str:phone_number>/', sms_views.phone_verification_view, name='phone_verification'),
    path('verify-phone/', sms_views.phone_verification_view, name='phone_verification_no_param'),
    path('resend-code/', sms_views.resend_verification_code_view, name='resend_verification_code'),
    path('sms-preferences/', sms_views.sms_preferences_view, name='sms_preferences'),
    path('verify-my-phone/', sms_views.verify_phone_for_user, name='verify_my_phone'),
    path('sms-status/', sms_views.sms_verification_status, name='sms_verification_status'),
    path('webhook/twilio/', sms_views.twilio_webhook, name='twilio_webhook'),
]