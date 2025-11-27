from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from applicants.models import Applicant, ApplicantCRM, InteractionLog
from buildings.models import Building
from applications.models import Application
from apartments.models import Apartment
from unittest.mock import patch

User = get_user_model()

class BrokerPermissionTests(TestCase):
    def setUp(self):
        self.client = Client()
        
        # Create Users
        self.admin = User.objects.create_superuser('admin', 'admin@example.com', 'password')
        self.broker_assigned = User.objects.create_user('broker1', 'broker1@example.com', 'password', is_broker=True)
        self.broker_unassigned = User.objects.create_user('broker2', 'broker2@example.com', 'password', is_broker=True)
        self.random_user = User.objects.create_user('user', 'user@example.com', 'password')
        
        # Create Applicant
        self.applicant = Applicant.objects.create(
            user=User.objects.create_user('applicant', 'app@example.com', 'password'),
            first_name="John",
            last_name="Doe",
            email="john@example.com",
            assigned_broker=self.broker_assigned
        )
        
        # Create Building and Apartment
        self.building = Building.objects.create(name="Test Building", street_address="123 Main St")
        self.building.brokers.add(self.broker_assigned)
        
        self.apartment = Apartment.objects.create(building=self.building, unit_number="101", rent_price=1000)

    def test_applicant_crm_access(self):
        # Admin should access
        self.client.force_login(self.admin)
        response = self.client.get(reverse('applicant_crm', args=[self.applicant.id]))
        self.assertEqual(response.status_code, 200)
        
        # Assigned Broker should access
        self.client.force_login(self.broker_assigned)
        response = self.client.get(reverse('applicant_crm', args=[self.applicant.id]))
        self.assertEqual(response.status_code, 200)
        
        # Unassigned Broker should NOT access (403 or redirect)
        self.client.force_login(self.broker_unassigned)
        response = self.client.get(reverse('applicant_crm', args=[self.applicant.id]))
        # Expecting redirect to list or 403. View redirects to 'applicants_list' on failure
        self.assertEqual(response.status_code, 302) 
        self.assertTrue('applicants' in response.url)

    def test_applicants_list_filtering(self):
        # Create another applicant unassigned to anyone
        other_applicant = Applicant.objects.create(
            user=User.objects.create_user('other', 'other@example.com', 'password'),
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com"
        )
        
        # Admin sees all
        self.client.force_login(self.admin)
        response = self.client.get(reverse('applicants_list'))
        self.assertContains(response, "John")
        self.assertContains(response, "Jane")
        
        # Assigned Broker sees only assigned
        self.client.force_login(self.broker_assigned)
        response = self.client.get(reverse('applicants_list'))
        self.assertContains(response, "John")
        self.assertNotContains(response, "Jane")
        
        # Unassigned Broker sees nothing
        self.client.force_login(self.broker_unassigned)
        response = self.client.get(reverse('applicants_list'))
        self.assertNotContains(response, "John")
        self.assertNotContains(response, "Jane")

    @patch('applications.nudge_service.NudgeService.send_nudge')
    def test_nudge_integration(self, mock_send_nudge):
        self.client.force_login(self.broker_assigned)
        
        # Mock return value
        mock_send_nudge.return_value = (True, None)
        
        response = self.client.post(reverse('applicant_crm', args=[self.applicant.id]), {
            'contact_method': 'email',
            'message': 'Test Nudge'
        })
        
        self.assertTrue(mock_send_nudge.called)
        # Check arguments
        args, kwargs = mock_send_nudge.call_args
        self.assertEqual(args[0], self.applicant) # target
        self.assertEqual(args[1], self.broker_assigned) # user
        self.assertEqual(kwargs['nudge_type'], 'email')
        self.assertEqual(kwargs['custom_message'], 'Test Nudge')
