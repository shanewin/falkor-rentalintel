"""
Test SSN encryption functionality
Run with: docker-compose exec web python manage.py test applications.test_encryption
"""
from django.test import TestCase
from django.db import connection
from applications.models import Application, PersonalInfoData
from apartments.models import Apartment, Building
from applicants.models import Applicant
from datetime import date
import uuid


class SSNEncryptionTest(TestCase):
    def setUp(self):
        """Set up test data"""
        # Create test building
        self.building = Building.objects.create(
            name="Test Building",
            street_address_1="123 Test St",
            city="New York",
            state="NY",
            zip_code="10001"
        )
        
        # Create test apartment
        self.apartment = Apartment.objects.create(
            building=self.building,
            unit_number="1A",
            rent_price=2000.00,
            status='available'
        )
        
        # Create test applicant
        self.applicant = Applicant.objects.create(
            first_name="Test",
            last_name="User",
            email="test@example.com",
            date_of_birth=date(1990, 1, 1),
            phone_number="555-1234"
        )
        
        # Create test application
        self.application = Application.objects.create(
            apartment=self.apartment,
            applicant=self.applicant,
            application_version='v2'
        )
        
        # Test SSN
        self.test_ssn = "123-45-6789"
    
    def test_ssn_encryption_and_decryption(self):
        """Test that SSN is encrypted in database but decrypted in Django"""
        
        # Create PersonalInfoData with SSN
        personal_info = PersonalInfoData.objects.create(
            application=self.application,
            first_name="John",
            last_name="Doe",
            email="john.doe@example.com",
            phone_cell="555-1234",
            date_of_birth=date(1990, 1, 1),
            ssn=self.test_ssn,
            current_address="123 Main St",
            address_duration="2 years",
            desired_address="456 New St",
            desired_unit="2B",
            desired_move_in_date=date(2024, 3, 1),
            referral_source="Online",
            reference1_name="Jane Smith",
            reference1_phone="555-5678"
        )
        
        # Test 1: SSN is decrypted when accessed through Django ORM
        retrieved_info = PersonalInfoData.objects.get(pk=personal_info.pk)
        self.assertEqual(retrieved_info.ssn, self.test_ssn)
        print(f"✓ Django ORM returns decrypted SSN: {retrieved_info.ssn}")
        
        # Test 2: SSN is encrypted in the database
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ssn FROM applications_personalinfodata WHERE id = %s",
                [personal_info.pk]
            )
            row = cursor.fetchone()
            encrypted_ssn = row[0] if row else None
        
        # Verify the database value is encrypted (not equal to original)
        self.assertIsNotNone(encrypted_ssn)
        self.assertNotEqual(encrypted_ssn, self.test_ssn)
        print(f"✓ Database contains encrypted value: {encrypted_ssn[:20]}...")
        
        # Test 3: Verify encryption is consistent
        personal_info.ssn = self.test_ssn
        personal_info.save()
        
        # Re-fetch from database
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ssn FROM applications_personalinfodata WHERE id = %s",
                [personal_info.pk]
            )
            row = cursor.fetchone()
            new_encrypted_ssn = row[0] if row else None
        
        # The encrypted value should be the same for the same input
        self.assertEqual(encrypted_ssn, new_encrypted_ssn)
        print("✓ Encryption is consistent for same input")
        
        # Test 4: Different SSNs produce different encrypted values
        different_ssn = "987-65-4321"
        personal_info.ssn = different_ssn
        personal_info.save()
        
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ssn FROM applications_personalinfodata WHERE id = %s",
                [personal_info.pk]
            )
            row = cursor.fetchone()
            different_encrypted_ssn = row[0] if row else None
        
        self.assertNotEqual(encrypted_ssn, different_encrypted_ssn)
        print("✓ Different SSNs produce different encrypted values")
        
        # Test 5: Can search by SSN (django-encrypted-model-fields supports this)
        found = PersonalInfoData.objects.filter(ssn=different_ssn).first()
        self.assertIsNotNone(found)
        self.assertEqual(found.pk, personal_info.pk)
        print("✓ Can search by encrypted field value")
        
    def test_ssn_encryption_with_null_values(self):
        """Test that null/empty SSNs are handled properly"""
        
        # Create PersonalInfoData without SSN (if field allows null)
        # Note: You may need to make SSN nullable in the model if required
        personal_info = PersonalInfoData.objects.create(
            application=self.application,
            first_name="Jane",
            last_name="Smith",
            email="jane.smith@example.com",
            phone_cell="555-9999",
            date_of_birth=date(1985, 5, 15),
            ssn="",  # Empty string
            current_address="789 Oak St",
            address_duration="1 year",
            desired_address="456 New St",
            desired_unit="3C",
            desired_move_in_date=date(2024, 3, 1),
            referral_source="Referral",
            reference1_name="Bob Jones",
            reference1_phone="555-1111"
        )
        
        # Verify empty string is handled
        retrieved_info = PersonalInfoData.objects.get(pk=personal_info.pk)
        self.assertEqual(retrieved_info.ssn, "")
        print("✓ Empty SSN values are handled correctly")


class EncryptionManualTest:
    """Manual test helper to verify encryption in real database"""
    
    @staticmethod
    def check_encryption():
        """
        Run this in Django shell to manually verify encryption:
        
        docker-compose exec web python manage.py shell
        >>> from applications.test_encryption import EncryptionManualTest
        >>> EncryptionManualTest.check_encryption()
        """
        from applications.models import PersonalInfoData
        from django.db import connection
        
        # Get any PersonalInfoData record
        personal_info = PersonalInfoData.objects.first()
        if not personal_info:
            print("No PersonalInfoData records found")
            return
        
        print(f"Django ORM SSN value: {personal_info.ssn}")
        
        # Check raw database value
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ssn FROM applications_personalinfodata WHERE id = %s",
                [personal_info.pk]
            )
            row = cursor.fetchone()
            if row:
                print(f"Raw database SSN value: {row[0]}")
                print(f"Encrypted: {row[0] != personal_info.ssn}")
            else:
                print("No row found")