from django.urls import path
from .views import (
    # Updated views for 5-section system
    broker_create_application, broker_confirmation, create_v2_application, v2_application_overview, v2_section1_personal_info,
    v2_section2_income, v2_section3_legal, v2_section4_review, v2_section5_payment,
    v2_section_navigation, add_previous_address, remove_previous_address,
    # Separated broker and applicant interfaces
    broker_application_management, applicant_application_interface,
    # Keep existing views for file management and analysis
    application, application_detail, applicant_complete, application_list, 
    delete_uploaded_file, application_edit, analyze_uploaded_file, check_analysis_status, send_application_link, test_email_send, test_sms_send,
    application_preview, broker_prefill_dashboard, broker_prefill_section1, prefill_status_api
)
from .account_views import create_account_after_application, application_completion_success

urlpatterns = [
    # Enhanced Broker Application Creation
    path('broker/create/', broker_create_application, name='broker_create_application'),
    path('broker/confirmation/<int:application_id>/', broker_confirmation, name='broker_confirmation'),
    
    # 5-Section Application System
    path('create/<int:apartment_id>/', create_v2_application, name='create_application'),
    path('create/', create_v2_application, name='create_application_no_apartment'),  # New: create without apartment
    path('new/<int:apartment_id>/', create_v2_application, name='application_form'),  # Alias for compatibility
    path('new/', application, name='application_form_legacy'),  # Legacy form without apartment requirement
    
    # Section-based application flow
    path('<int:application_id>/', v2_application_overview, name='application_detail'),
    path('<int:application_id>/overview/', v2_application_overview, name='v2_application_overview'),
    path('<int:application_id>/manage/', broker_application_management, name='broker_application_management'),
    path('<int:application_id>/section1/', v2_section1_personal_info, name='section1_personal_info'),
    path('<int:application_id>/section2/', v2_section2_income, name='section2_income'),
    path('<int:application_id>/section3/', v2_section3_legal, name='section3_legal'),
    path('<int:application_id>/section4/', v2_section4_review, name='section4_review'),
    path('<int:application_id>/section5/', v2_section5_payment, name='section5_payment'),
    
    # Section navigation
    path('<int:application_id>/section/<int:section_number>/', v2_section_navigation, name='section_navigation'),
    
    # AJAX endpoints for previous addresses
    path('<int:application_id>/add-address/', add_previous_address, name='add_previous_address'),
    path('<int:application_id>/remove-address/<int:address_id>/', remove_previous_address, name='remove_previous_address'),

    # Applicant completion (keep existing)
    path('<uuid:uuid>/complete/', applicant_complete, name='applicant_complete'),

    # Application management
    path('', application_list, name='applications_list'),
    path('<int:application_id>/edit/', application_edit, name='application_edit'),
    path('<int:application_id>/send-link/', send_application_link, name='send_application_link'),
    path('test-email/', test_email_send, name='test_email_send'),
    path('test-sms/', test_sms_send, name='test_sms_send'),
    path('<int:application_id>/preview/', application_preview, name='application_preview'),
    path('<int:application_id>/broker-prefill/', broker_prefill_dashboard, name='broker_prefill_dashboard'),
    path('<int:application_id>/broker-prefill/section1/', broker_prefill_section1, name='broker_prefill_section1'),
    path('<int:application_id>/prefill-status/', prefill_status_api, name='prefill_status_api'),
    
    # File management
    path('delete-file/<int:file_id>/', delete_uploaded_file, name='delete_uploaded_file'),
    path("file/<int:file_id>/analyze/", analyze_uploaded_file, name="analyze_uploaded_file"),
    path("file/<int:file_id>/status/", check_analysis_status, name="check_analysis_status"),
    
    # Account creation after application completion
    path('<uuid:uuid>/create-account/', create_account_after_application, name='create_account_after_application'),
    path('<uuid:uuid>/success/', application_completion_success, name='application_completion_success'),
]

