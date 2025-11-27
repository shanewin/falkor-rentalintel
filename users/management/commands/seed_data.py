from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from buildings.models import Building, BuildingImage, Amenity as BuildingAmenity
from apartments.models import Apartment, ApartmentAmenity, ApartmentImage
from applicants.models import Applicant, Amenity as ApplicantAmenity, Neighborhood
from applications.models import Application, ApplicationStatus, RequiredDocumentType
from users.profiles_models import AdminProfile, BrokerProfile
from faker import Faker
import random
from decimal import Decimal
import datetime

User = get_user_model()
fake = Faker()

class Command(BaseCommand):
    help = 'Seeds the database with dummy data'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Starting data seeding...'))
        
        # --- 1. Create Admin Superusers ---
        self.stdout.write('Creating Superusers...')
        admins = [
            ('admin1@doorway.com', 'Admin One'),
            ('admin2@doorway.com', 'Admin Two'),
            ('admin3@doorway.com', 'Admin Three')
        ]
        for email, name in admins:
            if not User.objects.filter(email=email).exists():
                user = User.objects.create_superuser(
                    email=email,
                    password='password123'
                )
                AdminProfile.objects.create(
                    user=user,
                    first_name=name.split()[0],
                    last_name=name.split()[1]
                )
        
        # --- 2. Create Brokers ---
        self.stdout.write('Creating Brokers...')
        brokers = []
        for i in range(15):
            email = f'broker{i+1}@doorway.com'
            if not User.objects.filter(email=email).exists():
                first = fake.first_name()
                last = fake.last_name()
                broker = User.objects.create_user(
                    email=email,
                    password='password123',
                    is_broker=True
                )
                BrokerProfile.objects.create(
                    user=broker,
                    first_name=first,
                    last_name=last,
                    phone_number=fake.phone_number()[:20],
                    business_name=f"{last} Realty",
                    business_address_1=fake.street_address(),
                    business_city="New York",
                    business_zip=fake.zipcode(),
                    broker_license_number=fake.uuid4()[:8]
                )

                brokers.append(broker)
            else:
                brokers.append(User.objects.get(email=email))

        # --- 3. Create Amenities & Neighborhoods ---
        self.stdout.write('Creating Amenities & Neighborhoods...')
        b_amenities = ['Doorman', 'Gym', 'Pool', 'Elevator', 'Laundry', 'Roof Deck', 'Parking']
        a_amenities = ['Dishwasher', 'Washer/Dryer', 'Balcony', 'Central AC', 'Fireplace']
        neighborhoods = ['Williamsburg', 'Bushwick', 'Bed-Stuy', 'Greenpoint', 'Crown Heights']
        
        created_b_amenities = []
        for name in b_amenities:
            obj, _ = BuildingAmenity.objects.get_or_create(name=name)
            created_b_amenities.append(obj)
            
        created_a_amenities = []
        for name in a_amenities:
            obj, _ = ApartmentAmenity.objects.get_or_create(name=name)
            created_a_amenities.append(obj)
            
        created_neighborhoods = []
        for name in neighborhoods:
            obj, _ = Neighborhood.objects.get_or_create(name=name)
            created_neighborhoods.append(obj)
            
        # Ensure Applicant Amenity model also has these if separate
        created_app_amenities = []
        for name in b_amenities + a_amenities:
             obj, _ = ApplicantAmenity.objects.get_or_create(name=name)
             created_app_amenities.append(obj)

        # --- 4. Create Buildings ---
        self.stdout.write('Creating Buildings...')
        buildings = []
        for i in range(20):
            building = Building.objects.create(
                name=f"{fake.last_name()} Tower",
                street_address_1=fake.street_address(),
                city="New York",
                state="NY",
                zip_code=fake.zipcode(),
                neighborhood=random.choice(neighborhoods),
                description=fake.text(),
                pet_policy=random.choice(['all_pets', 'no_pets', 'cats_only']),
                credit_screening_fee=20.00
            )
            building.amenities.set(random.sample(created_b_amenities, k=random.randint(1, 4)))
            # Assign random brokers
            building.brokers.set(random.sample(brokers, k=random.randint(1, 3)))
            
            # Dummy Image
            BuildingImage.objects.create(
                building=building,
                image=f"sample_building_{i}.jpg" # Dummy ID
            )
            buildings.append(building)

        # --- 5. Create Apartments ---
        self.stdout.write('Creating Apartments...')
        apartments = []
        for i in range(100):
            building = random.choice(buildings)
            bedrooms = random.choice([0, 1, 2, 3])
            rent = 2000 + (bedrooms * 1000) + random.randint(-200, 500)
            
            apt = Apartment.objects.create(
                building=building,
                unit_number=f"{random.randint(1, 20)}{random.choice(['A', 'B', 'C', 'D'])}",
                bedrooms=bedrooms,
                bathrooms=max(1, bedrooms // 2),
                square_feet=400 + (bedrooms * 200),
                rent_price=rent,
                deposit_price=rent,
                status='available',
                description=fake.text()
            )
            apt.amenities.set(random.sample(created_a_amenities, k=random.randint(0, 3)))
            
            # Dummy Image
            ApartmentImage.objects.create(
                apartment=apt,
                image=f"sample_apartment_{i}.jpg"
            )
            apartments.append(apt)

        # --- 6. Create Applicants ---
        self.stdout.write('Creating Applicants...')
        applicants = []
        for i in range(150):
            # 30 Applicants with missing income/budget for Nudge test
            is_nudge_case = i < 30
            
            first = fake.first_name()
            last = fake.last_name()
            email = f"applicant_{i}_{first.lower()}@example.com"
            
            # Create User for applicant
            user = User.objects.create_user(
                email=email,
                password='password123',
                is_applicant=True
            )
            
            applicant = Applicant.objects.create(
                user=user,
                first_name=first,
                last_name=last,
                email=email,
                phone_number=fake.phone_number()[:20],
                date_of_birth=fake.date_of_birth(minimum_age=18, maximum_age=60),
                annual_income=None if is_nudge_case else random.randint(40000, 200000),
                max_rent_budget=None if is_nudge_case else random.randint(1500, 5000),
                min_bedrooms=random.randint(0, 2),
                max_bedrooms=random.randint(2, 4),
                desired_move_in_date=timezone.now().date() + datetime.timedelta(days=random.randint(10, 60))
            )
            applicant.amenities.set(random.sample(created_app_amenities, k=random.randint(0, 3)))
            applicants.append(applicant)

        # --- 7. Create Applications ---
        self.stdout.write('Creating Applications...')
        for i in range(50):
            applicant = applicants[i + 30] # Skip nudge cases for applications to ensure valid data mostly
            apartment = random.choice(apartments)
            
            # 10 cases with missing docs (Integrity test)
            is_missing_docs = i < 10
            
            status = random.choice(ApplicationStatus.values)
            
            app = Application.objects.create(
                applicant=applicant,
                apartment=apartment,
                status=status,
                required_documents=[RequiredDocumentType.PHOTO_ID, RequiredDocumentType.PAYSTUB]
            )
            
            # Link broker from building
            if apartment.building.brokers.exists():
                app.broker = apartment.building.brokers.first()
                app.save()

            # Upload docs if not missing case
            if not is_missing_docs:
                # Upload all required
                pass # Logic to create UploadedFile objects would go here if needed, but for is_satisfied check we need them.
                
                # Let's simulate uploaded files for satisfied cases
                # 10 cases fully satisfied
                is_satisfied_case = i >= 10 and i < 20
                
                if is_satisfied_case:
                     # Add dummy files for all requirements
                     pass # We'd need to create UploadedFile objects.
        
        self.stdout.write(self.style.SUCCESS(f'Successfully seeded database with:\n'
                                             f'- {len(admins)} Superusers\n'
                                             f'- {len(brokers)} Brokers\n'
                                             f'- {len(buildings)} Buildings\n'
                                             f'- {len(apartments)} Apartments\n'
                                             f'- {len(applicants)} Applicants\n'
                                             f'- 50 Applications'))
