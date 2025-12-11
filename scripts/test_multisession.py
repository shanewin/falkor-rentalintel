#!/usr/bin/env python3
"""
Comprehensive test script for UUID application multi-session functionality
Tests save-and-continue, progress persistence, and cross-session data integrity
"""
import os
import sys
import django
from django.test import override_settings

# Setup Django
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate.settings')
django.setup()

from django.test import TestCase, Client
from django.urls import reverse
import json
from datetime import datetime
from applications.models import Application, PersonalInfoData, ApplicationSection, SectionStatus
from users.models import User

class MultiSessionTester:
    def __init__(self):
        self.client = Client()
        self.test_results = []
        # Set proper host header for all requests
        self.client.defaults['HTTP_HOST'] = 'localhost:8000'
        
    def log_test(self, test_name, passed, message):
        """Log test results"""
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
        if message:
            print(f"    {message}")
        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'message': message,
            'timestamp': datetime.now()
        })
    
    def setup_test_application(self):
        """Create a test application for testing"""
        try:
            # Get or create a broker user
            broker, created = User.objects.get_or_create(
                email='test_broker@example.com',
                defaults={
                    'is_broker': True
                }
            )
            
            # Create a test application
            application = Application.objects.create(
                broker=broker,
                manual_building_address="123 Test Street",
                manual_unit_number="4B",
                application_version='v2'
            )
            
            # Create sections
            for i in range(1, 6):
                ApplicationSection.objects.get_or_create(
                    application=application,
                    section_number=i,
                    defaults={'status': SectionStatus.NOT_STARTED}
                )
            
            print(f"📝 Created test application with UUID: {application.unique_link}")
            return application
            
        except Exception as e:
            self.log_test("Setup Test Application", False, f"Error creating test application: {str(e)}")
            return None
    
    def test_uuid_access(self, application):
        """Test 1: Verify UUID link provides access without authentication"""
        try:
            # Test direct UUID access to overview
            url = f"{reverse('v2_application_overview', args=[application.id])}?token={application.unique_link}"
            response = self.client.get(url)
            
            if response.status_code == 200:
                self.log_test("UUID Access to Overview", True, f"Status: {response.status_code}")
            else:
                self.log_test("UUID Access to Overview", False, f"Status: {response.status_code}")
                return False
            
            # Test section 1 access with token
            url = f"{reverse('section1_personal_info', args=[application.id])}?token={application.unique_link}"
            response = self.client.get(url)
            
            if response.status_code == 200:
                self.log_test("UUID Access to Section 1", True, f"Status: {response.status_code}")
                return True
            else:
                self.log_test("UUID Access to Section 1", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("UUID Access", False, f"Error: {str(e)}")
            return False
    
    def test_partial_form_save(self, application):
        """Test 2: Partial form filling and saving"""
        try:
            # First session - partial data entry
            session_1_data = {
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john.doe@example.com',
                'phone_cell': '555-123-4567',
                # Intentionally leaving other fields blank
            }
            
            # Post partial data without completing section  
            url = f"{reverse('section1_personal_info', args=[application.id])}?token={application.unique_link}"
            response = self.client.post(url, data=session_1_data)
            
            # Check if PersonalInfoData was created/updated
            try:
                personal_info = PersonalInfoData.objects.get(application=application)
                if (personal_info.first_name == 'John' and 
                    personal_info.last_name == 'Doe' and 
                    personal_info.email == 'john.doe@example.com'):
                    self.log_test("Partial Data Save", True, "Personal info saved successfully")
                    return True
                else:
                    self.log_test("Partial Data Save", False, "Data not saved correctly")
                    return False
            except PersonalInfoData.DoesNotExist:
                self.log_test("Partial Data Save", False, "PersonalInfoData not created")
                return False
                
        except Exception as e:
            self.log_test("Partial Form Save", False, f"Error: {str(e)}")
            return False
    
    def test_session_persistence(self, application):
        """Test 3: Data persistence across sessions"""
        try:
            # Simulate returning to the form in a new session
            url = f"{reverse('section1_personal_info', args=[application.id])}?token={application.unique_link}"
            response = self.client.get(url)
            
            if response.status_code != 200:
                self.log_test("Session Persistence", False, f"Cannot access form: {response.status_code}")
                return False
            
            # Check if previously saved data is present
            try:
                personal_info = PersonalInfoData.objects.get(application=application)
                if (personal_info.first_name == 'John' and 
                    personal_info.last_name == 'Doe' and 
                    personal_info.email == 'john.doe@example.com'):
                    self.log_test("Session Persistence", True, "Previously saved data is preserved")
                    return True
                else:
                    self.log_test("Session Persistence", False, "Previously saved data was lost")
                    return False
            except PersonalInfoData.DoesNotExist:
                self.log_test("Session Persistence", False, "PersonalInfoData does not exist")
                return False
                
        except Exception as e:
            self.log_test("Session Persistence", False, f"Error: {str(e)}")
            return False
    
    def test_complete_section_save(self, application):
        """Test 4: Complete section and check progress tracking"""
        try:
            # Complete the section with full data
            complete_data = {
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john.doe@example.com',
                'phone_cell': '555-123-4567',
                'date_of_birth': '1990-01-01',
                'current_address': '456 Current Street',
                'desired_address': '123 Test Street',
                'desired_unit': '4B',
                'desired_move_in_date': '2025-08-01',
                'has_pets': False,
                'save_continue': 'Save & Continue'
            }
            
            url = f"{reverse('section1_personal_info', args=[application.id])}?token={application.unique_link}"
            response = self.client.post(url, data=complete_data)
            
            # Check section status update
            section = ApplicationSection.objects.get(
                application=application,
                section_number=1
            )
            
            if section.status == SectionStatus.COMPLETED:
                self.log_test("Section Completion", True, "Section 1 marked as completed")
            else:
                self.log_test("Section Completion", False, f"Section status: {section.status}")
                return False
            
            # Check if application current_section was updated
            application.refresh_from_db()
            if application.current_section == 2:
                self.log_test("Progress Tracking", True, "Application moved to section 2")
                return True
            else:
                self.log_test("Progress Tracking", False, f"Current section: {application.current_section}")
                return False
                
        except Exception as e:
            self.log_test("Complete Section Save", False, f"Error: {str(e)}")
            return False
    
    def test_progress_indicators(self, application):
        """Test 5: Progress indicators and section status"""
        try:
            # Get overview page to check progress
            url = f"{reverse('v2_application_overview', args=[application.id])}?token={application.unique_link}"
            response = self.client.get(url)
            
            if response.status_code != 200:
                self.log_test("Progress Indicators", False, f"Cannot access overview: {response.status_code}")
                return False
            
            # Check context data
            context = response.context
            if context['completed_sections'] >= 1:
                self.log_test("Progress Count", True, f"Completed sections: {context['completed_sections']}")
            else:
                self.log_test("Progress Count", False, f"Completed sections: {context['completed_sections']}")
                return False
            
            if context['progress_percent'] > 0:
                self.log_test("Progress Percentage", True, f"Progress: {context['progress_percent']:.1f}%")
                return True
            else:
                self.log_test("Progress Percentage", False, f"Progress: {context['progress_percent']:.1f}%")
                return False
                
        except Exception as e:
            self.log_test("Progress Indicators", False, f"Error: {str(e)}")
            return False
    
    def test_cross_device_access(self, application):
        """Test 6: Same UUID from different 'device' (new client)"""
        try:
            # Create a new client to simulate different device/browser
            new_client = Client()
            
            url = f"{reverse('v2_application_overview', args=[application.id])}?token={application.unique_link}"
            response = new_client.get(url)
            
            if response.status_code == 200:
                self.log_test("Cross-Device Access", True, "UUID works from different client")
            else:
                self.log_test("Cross-Device Access", False, f"Status: {response.status_code}")
                return False
            
            # Check if data is still accessible
            url = f"{reverse('section1_personal_info', args=[application.id])}?token={application.unique_link}"
            response = new_client.get(url)
            
            if response.status_code == 200:
                self.log_test("Cross-Device Data Access", True, "Data accessible from different client")
                return True
            else:
                self.log_test("Cross-Device Data Access", False, f"Status: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Cross-Device Access", False, f"Error: {str(e)}")
            return False
    
    def test_invalid_token(self):
        """Test 7: Invalid token handling"""
        try:
            # Try with invalid UUID
            url = f"{reverse('v2_application_overview', args=[1])}?token=invalid-uuid-token"
            response = self.client.get(url)
            
            # Should redirect or show error
            if response.status_code in [302, 403, 404]:
                self.log_test("Invalid Token Handling", True, f"Properly rejected invalid token: {response.status_code}")
                return True
            else:
                self.log_test("Invalid Token Handling", False, f"Did not reject invalid token: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Invalid Token Handling", False, f"Error: {str(e)}")
            return False
    
    def test_data_integrity(self, application):
        """Test 8: Data integrity and no overwrites"""
        try:
            # Check that previously saved data is still intact
            personal_info = PersonalInfoData.objects.get(application=application)
            
            expected_data = {
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'john.doe@example.com',
                'phone_cell': '555-123-4567',
                'current_address': '456 Current Street',
                'desired_address': '123 Test Street',
                'desired_unit': '4B'
            }
            
            data_intact = True
            for field, expected_value in expected_data.items():
                actual_value = getattr(personal_info, field)
                if actual_value != expected_value:
                    data_intact = False
                    break
            
            if data_intact:
                self.log_test("Data Integrity", True, "All saved data remains intact")
                return True
            else:
                self.log_test("Data Integrity", False, "Some data was corrupted or lost")
                return False
                
        except Exception as e:
            self.log_test("Data Integrity", False, f"Error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run comprehensive multi-session tests"""
        print("🧪 STARTING COMPREHENSIVE MULTI-SESSION TESTS")
        print("=" * 60)
        
        # Setup
        application = self.setup_test_application()
        if not application:
            print("❌ Cannot proceed - test application setup failed")
            return
        
        print(f"\n🔗 Test UUID Link: /applications/{application.id}/?token={application.unique_link}")
        print("\n🧪 Running Tests...")
        
        # Run all tests
        tests_passed = 0
        total_tests = 8
        
        if self.test_uuid_access(application):
            tests_passed += 1
            
        if self.test_partial_form_save(application):
            tests_passed += 1
            
        if self.test_session_persistence(application):
            tests_passed += 1
            
        if self.test_complete_section_save(application):
            tests_passed += 1
            
        if self.test_progress_indicators(application):
            tests_passed += 1
            
        if self.test_cross_device_access(application):
            tests_passed += 1
            
        if self.test_invalid_token():
            tests_passed += 1
            
        if self.test_data_integrity(application):
            tests_passed += 1
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"Tests Passed: {tests_passed}/{total_tests}")
        print(f"Success Rate: {(tests_passed/total_tests)*100:.1f}%")
        
        if tests_passed == total_tests:
            print("🎉 ALL TESTS PASSED - Multi-session functionality is working!")
        else:
            print(f"⚠️  {total_tests - tests_passed} TESTS FAILED - Issues found")
        
        print(f"\n🔗 Manual Test URL: http://localhost:8000/applications/{application.id}/?token={application.unique_link}")
        print("💡 Use this URL to manually test the save-and-continue functionality")
        
        return tests_passed == total_tests


if __name__ == "__main__":
    tester = MultiSessionTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)