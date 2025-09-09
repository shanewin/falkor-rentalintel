"""
Django management command to test SSN encryption
Run with: docker-compose exec web python manage.py test_ssn_encryption
"""
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from applications.models import Application, PersonalInfoData
from apartments.models import Apartment, Building
from applicants.models import Applicant
from datetime import date


class Command(BaseCommand):
    help = 'Test SSN encryption functionality'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Testing SSN encryption...'))
        
        try:
            with transaction.atomic():
                # Create test data
                test_data = self.create_test_data()
                
                # Run encryption tests
                self.test_encryption(test_data)
                
                # Clean up (rollback transaction)
                raise Exception("Rolling back test data")
                
        except Exception as e:
            if "Rolling back" in str(e):
                self.stdout.write(self.style.SUCCESS('✓ Test completed successfully (data rolled back)'))
            else:
                self.stdout.write(self.style.ERROR(f'Test failed: {e}'))

    def create_test_data(self):
        """Create test data for encryption testing"""
        self.stdout.write('Creating test data...')
        
        # Create building if it doesn't exist
        building, _ = Building.objects.get_or_create(
            name="Test Encryption Building",
            defaults={
                'street_address_1': '123 Test St',
                'city': 'New York',
                'state': 'NY',
                'zip_code': '10001'
            }
        )
        
        # Create apartment
        apartment, _ = Apartment.objects.get_or_create(
            building=building,
            unit_number="TEST1",
            defaults={
                'rent_price': 2000.00,
                'status': 'available'
            }
        )
        
        # Create applicant
        applicant, _ = Applicant.objects.get_or_create(
            email="encryption.test@example.com",
            defaults={
                'first_name': 'Test',
                'last_name': 'Encryption',
                'date_of_birth': date(1990, 1, 1),
                'phone_number': '555-TEST'
            }
        )
        
        # Create application
        application, _ = Application.objects.get_or_create(
            apartment=apartment,
            applicant=applicant,
            defaults={'application_version': 'v2'}
        )
        
        return {
            'building': building,
            'apartment': apartment,
            'applicant': applicant,
            'application': application
        }

    def test_encryption(self, test_data):
        """Run encryption tests"""
        test_ssn = "123-45-6789"
        
        self.stdout.write('Creating PersonalInfoData with SSN...')
        
        # Create PersonalInfoData with SSN
        personal_info = PersonalInfoData.objects.create(
            application=test_data['application'],
            first_name="John",
            last_name="TestEncryption",
            email="john.encryption@example.com",
            phone_cell="555-1234",
            date_of_birth=date(1990, 1, 1),
            ssn=test_ssn,
            current_address="123 Test Address",
            address_duration="2 years",
            desired_address="456 Desired St",
            desired_unit="2B",
            desired_move_in_date=date(2024, 3, 1),
            referral_source="Test",
            reference1_name="Test Reference",
            reference1_phone="555-5678"
        )

        # Test 1: Django ORM returns decrypted value
        retrieved = PersonalInfoData.objects.get(pk=personal_info.pk)
        if retrieved.ssn == test_ssn:
            self.stdout.write(self.style.SUCCESS('✓ Django ORM returns decrypted SSN'))
        else:
            self.stdout.write(self.style.ERROR(f'✗ Django ORM mismatch: expected {test_ssn}, got {retrieved.ssn}'))

        # Test 2: Database contains encrypted value
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT ssn FROM applications_personalinfodata WHERE id = %s",
                [personal_info.pk]
            )
            row = cursor.fetchone()
            encrypted_ssn = row[0] if row else None

        if encrypted_ssn and encrypted_ssn != test_ssn:
            self.stdout.write(self.style.SUCCESS(f'✓ Database contains encrypted value: {encrypted_ssn[:20]}...'))
        else:
            self.stdout.write(self.style.ERROR('✗ SSN is not encrypted in database'))

        # Test 3: Search functionality works
        found = PersonalInfoData.objects.filter(ssn=test_ssn).first()
        if found and found.pk == personal_info.pk:
            self.stdout.write(self.style.SUCCESS('✓ Search by encrypted field works'))
        else:
            self.stdout.write(self.style.ERROR('✗ Search by encrypted field failed'))

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
            different_encrypted = row[0] if row else None

        if different_encrypted != encrypted_ssn:
            self.stdout.write(self.style.SUCCESS('✓ Different SSNs produce different encrypted values'))
        else:
            self.stdout.write(self.style.ERROR('✗ Different SSNs produce same encrypted value'))

        self.stdout.write(self.style.SUCCESS('\nEncryption Summary:'))
        self.stdout.write(f'  Original SSN: {test_ssn}')
        self.stdout.write(f'  Django ORM: {retrieved.ssn}')
        self.stdout.write(f'  Database: {encrypted_ssn[:30]}...')
        self.stdout.write(f'  Encrypted: {encrypted_ssn != test_ssn}')