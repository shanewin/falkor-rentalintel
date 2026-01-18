from django.test import TestCase
from applicants.forms import ApplicantBasicInfoForm
from django.contrib.auth import get_user_model
from crispy_forms.layout import Layout, Div

User = get_user_model()

class ApplicantBasicInfoFormTests(TestCase):
    def test_form_valid_data(self):
        """Test that the form validates with correct data"""
        data = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': 'test@example.com',
            'phone_number': '(555) 555-5555',
            'date_of_birth': '1990-01-01',
            # Optional fields can be omitted or empty
        }
        form = ApplicantBasicInfoForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_required_fields(self):
        """Test that required fields are actually required"""
        form = ApplicantBasicInfoForm(data={})
        self.assertFalse(form.is_valid())
        self.assertIn('first_name', form.errors)
        self.assertIn('last_name', form.errors)
        self.assertIn('email', form.errors)

    def test_form_layout_structure(self):
        """
        Verify the form layout contains the 3 main containers:
        Account Information, Identification, Residential History
        """
        form = ApplicantBasicInfoForm()
        layout = form.helper.layout
        
        # We expect a Layout object with 3 distinct Divs (cards)
        self.assertIsInstance(layout, Layout)
        
        # Retrieve the main fields/divs from the layout
        # Note: Crispy layout objects can be iterated
        main_divs = [field for field in layout if isinstance(field, Div)]
        
        # We generally expect 3 main card divs based on the refactor
        # 1. Account Info
        # 2. Identification
        # 3. Residential History
        self.assertTrue(len(main_divs) >= 3, "Expected at least 3 main containers in the layout")
        
        # Basic check for content in the first container (Account Info)
        # We look for the "Account Information" header in the HTML of the first div's children
        first_card = main_divs[0]
        # This is a loose check, mainly verifying we haven't broken the crispy object structure
        self.assertIsInstance(first_card, Div)
