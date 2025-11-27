"""
Comprehensive test suite for the apartments app.
Business Context: Testing core rental unit functionality that drives revenue.
Ensures apartment listings, pricing, and broker contact features work correctly.
"""

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.core import mail
from decimal import Decimal
from .models import Apartment, ApartmentImage, ApartmentAmenity, ApartmentConcession
from buildings.models import Building, Amenity
from .forms import ApartmentForm, ApartmentBasicForm, ApartmentAmenitiesForm, ApartmentDetailsForm
import json

User = get_user_model()


class ApartmentModelTest(TestCase):
    """
    Test apartment model functionality.
    Business Impact: Validates core data integrity for rental inventory.
    """
    
    def setUp(self):
        """Create test data for apartment tests"""
        # Create test building
        self.building = Building.objects.create(
            name="Test Tower",
            street_address_1="123 Test St",
            city="New York",
            state="NY",
            zip_code="10001",
            neighborhood="midtown"
        )
        
        # Create test apartment
        self.apartment = Apartment.objects.create(
            building=self.building,
            unit_number="12A",
            bedrooms=2,
            bathrooms=1.5,
            square_feet=850,
            rent_price=Decimal("3500.00"),
            status="available",
            apartment_type="multi_family"
        )
        
    def test_apartment_creation(self):
        """
        Test apartment is created with correct attributes.
        Business Logic: Each apartment represents a rentable unit with specific pricing.
        """
        self.assertEqual(self.apartment.unit_number, "12A")
        self.assertEqual(self.apartment.bedrooms, 2)
        self.assertEqual(self.apartment.bathrooms, 1.5)
        self.assertEqual(self.apartment.square_feet, 850)
        self.assertEqual(self.apartment.rent_price, Decimal("3500.00"))
        self.assertEqual(self.apartment.status, "available")
        
    def test_apartment_string_representation(self):
        """
        Test apartment string representation.
        Business Logic: Clear identification for brokers managing multiple units.
        """
        expected = "Test Tower - Unit 12A"
        self.assertEqual(str(self.apartment), expected)
        
    def test_get_filled_fields(self):
        """
        Test get_filled_fields method returns correct data.
        Business Logic: Shows completeness of listing for quality control.
        """
        fields = self.apartment.get_filled_fields()
        self.assertEqual(fields["Unit Number"], "12A")
        self.assertEqual(fields["Bedrooms"], 2)
        self.assertEqual(fields["Square Feet"], 850)
        self.assertEqual(fields["Rent Price"], "$3500.00")
        self.assertEqual(fields["Status"], "Available")
        
    def test_apartment_amenities_relationship(self):
        """
        Test apartment can have multiple amenities.
        Business Logic: Amenities justify pricing and attract specific tenant segments.
        """
        amenity1 = ApartmentAmenity.objects.create(name="In-Unit Washer/Dryer")
        amenity2 = ApartmentAmenity.objects.create(name="Dishwasher")
        
        self.apartment.amenities.add(amenity1, amenity2)
        self.assertEqual(self.apartment.amenities.count(), 2)
        self.assertIn(amenity1, self.apartment.amenities.all())
        
    def test_apartment_concession(self):
        """
        Test concession creation and relationship.
        Business Logic: Concessions reduce effective rent to increase occupancy.
        """
        concession = ApartmentConcession.objects.create(
            apartment=self.apartment,
            months_free=1.5,
            lease_terms="14-month lease",
            name="Holiday Special"
        )
        
        self.assertEqual(self.apartment.concessions.count(), 1)
        self.assertEqual(str(concession), "Holiday Special - 1.5 months free - 14-month lease")


class ApartmentViewTest(TestCase):
    """
    Test apartment views functionality.
    Business Impact: Ensures user-facing features work correctly for lead generation.
    """
    
    def setUp(self):
        """Create test data and client"""
        self.client = Client()
        
        # Create test user (broker)
        self.user = User.objects.create_user(
            email="broker@test.com",
            password="testpass123"
        )
        
        # Create test building
        self.building = Building.objects.create(
            name="Luxury Heights",
            street_address_1="456 Park Ave",
            city="New York",
            state="NY",
            zip_code="10022",
            neighborhood="upper_east_side"
        )
        
        # Create test apartments with various configurations
        self.studio = Apartment.objects.create(
            building=self.building,
            unit_number="1A",
            bedrooms=0,
            bathrooms=1,
            square_feet=500,
            rent_price=Decimal("2500.00"),
            status="available"
        )
        
        self.one_bed = Apartment.objects.create(
            building=self.building,
            unit_number="2B",
            bedrooms=1,
            bathrooms=1,
            square_feet=700,
            rent_price=Decimal("3200.00"),
            status="available"
        )
        
        self.two_bed = Apartment.objects.create(
            building=self.building,
            unit_number="3C",
            bedrooms=2,
            bathrooms=2,
            square_feet=1100,
            rent_price=Decimal("4500.00"),
            status="rented"
        )
        
    def test_apartments_list_view(self):
        """
        Test apartments list page loads correctly.
        Business Logic: Main discovery page for prospective tenants.
        """
        response = self.client.get(reverse('apartments_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Luxury Heights")
        self.assertIn('apartments', response.context)
        
    def test_apartment_filtering_by_price(self):
        """
        Test price filtering functionality.
        Business Logic: Price is primary decision factor for tenants.
        """
        # Test under $3000 filter
        response = self.client.get(reverse('apartments_list'), {'price': 'under_2000'})
        self.assertEqual(response.status_code, 200)
        apartments = response.context['apartments']
        for apt in apartments:
            self.assertLess(apt.rent_price, 2000)
            
    def test_apartment_filtering_by_bedrooms(self):
        """
        Test bedroom count filtering.
        Business Logic: Bedroom count correlates with household size requirements.
        """
        response = self.client.get(reverse('apartments_list'), {'min_bedrooms': '1'})
        self.assertEqual(response.status_code, 200)
        apartments = response.context['apartments']
        # Should include 1 and 2 bedroom, but not studio
        self.assertIn(self.one_bed, apartments)
        self.assertIn(self.two_bed, apartments)
        
    def test_apartment_overview_view(self):
        """
        Test individual apartment details page.
        Business Logic: Conversion page where users decide to contact broker.
        """
        response = self.client.get(
            reverse('apartment_overview', kwargs={'apartment_id': self.studio.id})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unit 1A")
        self.assertContains(response, "$2,500")
        
    def test_ajax_apartment_filtering(self):
        """
        Test AJAX filtering returns JSON response.
        Business Logic: Seamless filtering improves user experience and engagement.
        """
        response = self.client.get(
            reverse('apartments_list'),
            {'max_price': '3000'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('apartments', data)
        self.assertIn('total_results', data)
        
    def test_contact_broker_tour_request(self):
        """
        Test broker contact form for tour requests.
        Business Logic: Primary lead capture mechanism for converting visitors to tenants.
        """
        response = self.client.post(
            reverse('contact_broker', kwargs={'apartment_id': self.studio.id}),
            {
                'name': 'John Tenant',
                'email': 'john@example.com',
                'phone': '555-1234',
                'contact_type': 'request_tour',
                'tour_type': 'in_person',
                'preferred_datetime_1': '2024-12-01T14:00'
            }
        )
        self.assertEqual(response.status_code, 302)  # Redirect after success
        
        # Check email was sent
        self.assertEqual(len(mail.outbox), 1)  # At least broker notification
        self.assertIn('Tour Request', mail.outbox[0].subject)
        self.assertIn('John Tenant', mail.outbox[0].body)
        
    def test_contact_broker_question(self):
        """
        Test broker contact form for questions.
        Business Logic: Pre-qualification through Q&A reduces unnecessary tours.
        """
        response = self.client.post(
            reverse('contact_broker', kwargs={'apartment_id': self.one_bed.id}),
            {
                'name': 'Jane Renter',
                'email': 'jane@example.com',
                'phone': '555-5678',
                'contact_type': 'ask_question',
                'question': 'Are pets allowed in this unit?'
            }
        )
        self.assertEqual(response.status_code, 302)
        
        # Check email content
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Question about', mail.outbox[0].subject)
        self.assertIn('Are pets allowed', mail.outbox[0].body)


class ApartmentFormTest(TestCase):
    """
    Test apartment forms functionality.
    Business Impact: Ensures data quality for apartment listings.
    """
    
    def setUp(self):
        """Create test data for forms"""
        self.building = Building.objects.create(
            name="Form Test Building",
            street_address_1="789 Form St",
            city="Boston",
            state="MA",
            zip_code="02101"
        )
        
    def test_apartment_basic_form_valid(self):
        """
        Test basic apartment form with valid data.
        Business Logic: Step 1 captures essential pricing and configuration.
        """
        form_data = {
            'building': self.building.id,
            'unit_number': '5A',
            'bedrooms': 2,
            'bathrooms': 1,
            'square_feet': 900,
            'apartment_type': 'multi_family',
            'rent_price': '3000.00',
            'status': 'available'
        }
        form = ApartmentBasicForm(data=form_data)
        self.assertTrue(form.is_valid())
        
    def test_apartment_basic_form_missing_required(self):
        """
        Test form validation for required fields.
        Business Logic: Prevents incomplete listings that can't generate leads.
        """
        form_data = {
            'building': self.building.id,
            # Missing unit_number and rent_price
            'bedrooms': 2
        }
        form = ApartmentBasicForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('unit_number', form.errors)
        self.assertIn('rent_price', form.errors)
        
    def test_apartment_amenities_form(self):
        """
        Test amenities form functionality.
        Business Logic: Detailed amenities help match apartments to tenant preferences.
        """
        amenity1 = ApartmentAmenity.objects.create(name="Gym")
        amenity2 = ApartmentAmenity.objects.create(name="Pool")
        
        apartment = Apartment.objects.create(
            building=self.building,
            unit_number="6B",
            rent_price=Decimal("2800.00")
        )
        
        form_data = {
            'amenities': [amenity1.id, amenity2.id],
            'lock_type': 'Smart Lock',
            'description': 'Beautiful apartment with great views'
        }
        form = ApartmentAmenitiesForm(data=form_data, instance=apartment)
        self.assertTrue(form.is_valid())
        
    def test_apartment_details_form(self):
        """
        Test additional details form.
        Business Logic: Captures leasing terms and requirements for transparency.
        """
        apartment = Apartment.objects.create(
            building=self.building,
            unit_number="7C",
            rent_price=Decimal("3200.00")
        )
        
        form_data = {
            'broker_fee_required': True,
            'paid_months': 2,
            'lease_duration': '12 months',
            'holding_deposit': '500.00',
            'free_stuff': 'Free month rent',
            'required_documents': 'Proof of income, references'
        }
        form = ApartmentDetailsForm(data=form_data, instance=apartment)
        self.assertTrue(form.is_valid())


class ApartmentMultiStepWorkflowTest(TestCase):
    """
    Test multi-step apartment creation workflow.
    Business Impact: Reduces abandonment rate by breaking complex form into steps.
    """
    
    def setUp(self):
        """Set up test client and data"""
        self.client = Client()
        self.user = User.objects.create_user(
            email="broker@workflow.com",
            password="testpass123"
        )
        self.client.login(email="broker@workflow.com", password="testpass123")
        
        self.building = Building.objects.create(
            name="Workflow Building",
            street_address_1="100 Process Ave",
            city="Chicago",
            state="IL",
            zip_code="60601"
        )
        
    def test_step1_basic_info(self):
        """
        Test step 1: Basic apartment information.
        Business Logic: Captures minimum viable listing data.
        """
        response = self.client.post(
            reverse('create_apartment_v2'),
            {
                'building': self.building.id,
                'unit_number': '10A',
                'bedrooms': 1,
                'bathrooms': 1,
                'square_feet': 650,
                'apartment_type': 'multi_family',
                'rent_price': '1800.00',
                'status': 'available',
                'apartment_submit': 'Save & Continue'
            }
        )
        
        # Should redirect to step 2
        self.assertEqual(response.status_code, 302)
        
        # Verify apartment was created
        apartment = Apartment.objects.get(unit_number='10A')
        self.assertEqual(apartment.building, self.building)
        self.assertEqual(apartment.square_feet, 650)
        
    def test_complete_workflow(self):
        """
        Test complete multi-step workflow.
        Business Logic: Ensures brokers can create complete listings efficiently.
        """
        # Step 1: Create apartment
        response = self.client.post(
            reverse('create_apartment_v2'),
            {
                'building': self.building.id,
                'unit_number': '11B',
                'bedrooms': 2,
                'bathrooms': 2,
                'square_feet': 1000,
                'apartment_type': 'multi_family',
                'rent_price': '2500.00',
                'status': 'available',
                'apartment_submit': 'Save & Continue'
            }
        )
        
        apartment = Apartment.objects.get(unit_number='11B')
        
        # Step 2: Skip images (test skip functionality)
        response = self.client.post(
            reverse('apartment_step2', kwargs={'apartment_id': apartment.id}),
            {'skip_images': 'Skip'}
        )
        self.assertEqual(response.status_code, 302)
        
        # Step 3: Add amenities
        amenity = ApartmentAmenity.objects.create(name="Balcony")
        response = self.client.post(
            reverse('apartment_step3', kwargs={'apartment_id': apartment.id}),
            {
                'amenities': [amenity.id],
                'lock_type': 'Keypad',
                'amenities_submit': 'Save & Continue'
            }
        )
        self.assertEqual(response.status_code, 302)
        
        # Step 4: Add details
        response = self.client.post(
            reverse('apartment_step4', kwargs={'apartment_id': apartment.id}),
            {
                'broker_fee_required': False,
                'lease_duration': '12 months',
                'details_submit': 'Complete'
            }
        )
        self.assertEqual(response.status_code, 302)
        
        # Verify final apartment state
        apartment.refresh_from_db()
        self.assertEqual(apartment.amenities.count(), 1)
        self.assertEqual(apartment.lock_type, 'Keypad')
        self.assertEqual(apartment.lease_duration, '12 months')


class ApartmentSearchTest(TestCase):
    """
    Test apartment search and filtering functionality.
    Business Impact: Effective search drives tenant-apartment matching and conversion.
    """
    
    def setUp(self):
        """Create diverse apartment inventory for testing"""
        self.client = Client()
        
        # Create multiple buildings in different neighborhoods
        self.building_ues = Building.objects.create(
            name="Upper East Side Towers",
            street_address_1="1000 Park Ave",
            city="New York",
            state="NY",
            zip_code="10021",
            neighborhood="upper_east_side"
        )
        
        self.building_bk = Building.objects.create(
            name="Brooklyn Heights",
            street_address_1="200 Court St",
            city="Brooklyn",
            state="NY",
            zip_code="11201",
            neighborhood="brooklyn_heights"
        )
        
        # Create amenities
        self.gym = Amenity.objects.create(name="Gym")
        self.doorman = Amenity.objects.create(name="Doorman")
        
        # Add amenities to buildings
        self.building_ues.amenities.add(self.gym, self.doorman)
        self.building_bk.amenities.add(self.gym)
        
        # Create apartments with different characteristics
        Apartment.objects.create(
            building=self.building_ues,
            unit_number="PH1",
            bedrooms=3,
            bathrooms=2.5,
            square_feet=2000,
            rent_price=Decimal("8000.00"),
            status="available"
        )
        
        Apartment.objects.create(
            building=self.building_bk,
            unit_number="4A",
            bedrooms=1,
            bathrooms=1,
            square_feet=750,
            rent_price=Decimal("2800.00"),
            status="available"
        )
        
    def test_neighborhood_filter(self):
        """
        Test filtering by neighborhood.
        Business Logic: Location preferences are critical for tenant satisfaction.
        """
        response = self.client.get(
            reverse('apartments_list'),
            {'neighborhoods': ['upper_east_side']}
        )
        self.assertEqual(response.status_code, 200)
        apartments = response.context['apartments']
        
        for apt in apartments:
            self.assertEqual(apt.building.neighborhood, 'upper_east_side')
            
    def test_amenity_filter(self):
        """
        Test filtering by building amenities.
        Business Logic: Premium amenities justify higher rents.
        """
        response = self.client.get(
            reverse('apartments_list'),
            {'amenities': [self.doorman.id]}
        )
        self.assertEqual(response.status_code, 200)
        apartments = response.context['apartments']
        
        # Only Upper East Side building has doorman
        for apt in apartments:
            self.assertEqual(apt.building, self.building_ues)
            
    def test_combined_filters(self):
        """
        Test multiple filters applied together.
        Business Logic: Complex filtering helps tenants find perfect match quickly.
        """
        response = self.client.get(
            reverse('apartments_list'),
            {
                'min_bedrooms': '1',
                'max_bedrooms': '2',
                'max_price': '3000',
                'amenities': [self.gym.id]
            }
        )
        self.assertEqual(response.status_code, 200)
        apartments = response.context['apartments']
        
        # Should only return Brooklyn apartment (1BR, $2800, has gym)
        self.assertEqual(apartments.count(), 1)
        self.assertEqual(apartments.first().building, self.building_bk)