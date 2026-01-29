"""
Generate fake applicant profiles for testing
Usage: docker-compose exec web python manage.py generate_fake_profile user@example.com
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
from applicants.models import Applicant, Pet, PreviousAddress
from users.models import User
from faker import Faker

fake = Faker()

class Command(BaseCommand):
    help = 'Generate a fake applicant profile for testing'

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='Email for the applicant')
        parser.add_argument('--full', action='store_true', help='Generate 100% complete profile')

    def handle(self, *args, **options):
        email = options['email']
        full_profile = options.get('full', False)
        
        # Get or create user
        user, created = User.objects.get_or_create(
            email=email,
            defaults={
                'is_applicant': True,
                'is_active': True
            }
        )
        
        if created:
            user.set_password('password123')
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Created user: {email}'))
        
        # Get or create applicant
        applicant, created = Applicant.objects.get_or_create(
            email=email,
            defaults={'user': user}
        )
        
        if not created:
            self.stdout.write(self.style.WARNING(f'Applicant already exists, updating...'))
        
        # Basic Information
        applicant.first_name = fake.first_name()
        applicant.last_name = fake.last_name()
        applicant.phone_number = fake.phone_number()[:20]
        applicant.date_of_birth = fake.date_of_birth(minimum_age=22, maximum_age=45)
        
        # Current Address
        applicant.street_address_1 = fake.street_address()
        applicant.street_address_2 = fake.secondary_address() if random.choice([True, False]) else None
        applicant.city = fake.city()
        applicant.state = random.choice(['NY', 'NJ', 'CT', 'PA', 'MA'])
        applicant.zip_code = fake.zipcode()[:10]
        applicant.length_at_current_address = random.choice([
            '6 months', '1 year', '2 years', '3 years', '5 years'
        ])
        applicant.housing_status = random.choice(['rent', 'own', 'family'])
        
        # Current Housing Details
        applicant.current_landlord_name = fake.name()
        applicant.current_landlord_phone = fake.phone_number()[:20]
        applicant.current_landlord_email = fake.email()
        applicant.monthly_rent = random.randint(1500, 3500)
        applicant.reason_for_moving = random.choice([
            'Job relocation',
            'Need more space',
            'Closer to work',
            'Better neighborhood',
            'Lease ending'
        ])
        
        # Housing Preferences
        applicant.desired_move_in_date = timezone.now().date() + timedelta(days=random.randint(30, 90))
        applicant.min_bedrooms = random.choice([1, 2])
        applicant.max_bedrooms = applicant.min_bedrooms + random.choice([0, 1])
        applicant.min_bathrooms = 1
        applicant.max_bathrooms = random.choice([1, 2])
        applicant.max_rent_budget = random.randint(2000, 4500)
        applicant.open_to_roommates = random.choice([True, False])
        
        # Identification
        applicant.driver_license_number = fake.bothify(text='??######')
        applicant.driver_license_state = applicant.state
        
        # Emergency Contact
        applicant.emergency_contact_name = fake.name()
        applicant.emergency_contact_relationship = random.choice([
            'Parent', 'Sibling', 'Spouse', 'Friend', 'Partner'
        ])
        applicant.emergency_contact_phone = fake.phone_number()[:20]
        
        # Employment Information
        applicant.employment_status = random.choice(['employed', 'self_employed', 'student'])
        applicant.company_name = fake.company()
        applicant.position = fake.job()
        applicant.annual_income = random.randint(50000, 120000)
        applicant.supervisor_name = fake.name()
        applicant.supervisor_email = fake.email()
        applicant.supervisor_phone = fake.phone_number()[:20]
        applicant.currently_employed = True
        applicant.employment_start_date = fake.date_between(start_date='-5y', end_date='-1y')
        
        if full_profile:
            # Student Information (if applicable)
            if random.choice([True, False]):
                applicant.school_name = fake.company() + ' University'
                applicant.year_of_graduation = random.randint(2020, 2026)
                applicant.school_address = fake.address()
                applicant.school_phone = fake.phone_number()[:20]
            
            # Rental History
            applicant.previous_landlord_name = fake.name()
            applicant.previous_landlord_contact = fake.phone_number()[:20]
            applicant.evicted_before = False
            
            # Placement Status
            applicant.placement_status = 'unplaced'
        
        applicant.save()
        
        # Add previous addresses
        if full_profile:
            PreviousAddress.objects.filter(applicant=applicant).delete()
            for i in range(random.randint(1, 3)):
                PreviousAddress.objects.create(
                    applicant=applicant,
                    order=i+1,
                    street_address_1=fake.street_address(),
                    city=fake.city(),
                    state=random.choice(['NY', 'NJ', 'CT']),
                    zip_code=fake.zipcode()[:10],
                    length_at_address=f'{random.randint(1, 3)} years',
                    housing_status='rent',
                    landlord_name=fake.name(),
                    landlord_phone=fake.phone_number()[:20]
                )
        
        # Add pets
        if full_profile and random.choice([True, False]):
            Pet.objects.filter(applicant=applicant).delete()
            for i in range(random.randint(1, 2)):
                Pet.objects.create(
                    applicant=applicant,
                    pet_type=random.choice(['dog', 'cat', 'bird', 'fish']),
                    name=fake.first_name(),
                    quantity=1,
                    description=f'Friendly and well-behaved'
                )
        
        # Calculate completion
        status = applicant.get_field_completion_status()
        completion = status['overall_completion_percentage']
        
        self.stdout.write(self.style.SUCCESS(
            f'\n✓ Generated profile for {applicant.first_name} {applicant.last_name}'
        ))
        self.stdout.write(self.style.SUCCESS(f'  Email: {email}'))
        self.stdout.write(self.style.SUCCESS(f'  Password: password123'))
        self.stdout.write(self.style.SUCCESS(f'  Completion: {completion}%'))
        self.stdout.write(self.style.SUCCESS(f'  Phone: {applicant.phone_number}'))
        self.stdout.write(self.style.SUCCESS(f'  Annual Income: ${applicant.annual_income:,}'))
        self.stdout.write(self.style.SUCCESS(f'  Max Budget: ${applicant.max_rent_budget:,}/mo'))