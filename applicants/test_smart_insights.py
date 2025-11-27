#!/usr/bin/env python
"""
Smart Insights Critical Bug Fix Validation Tests
===============================================

Tests all 4 critical fixes implemented in smart_insights.py:
1. Decimal precision for financial calculations
2. None vs 0 income handling
3. Fair Housing compliance (student scoring)
4. XSS protection in text output

Run this script to verify all fixes work correctly.
"""

import os
import sys
import django
from decimal import Decimal

# Setup Django environment
sys.path.append('/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate.settings')
django.setup()

from applicants.models import Applicant, ApplicantJob, ApplicantIncomeSource
from applicants.smart_insights import SmartInsights


class TestSmartInsights:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def assert_equal(self, actual, expected, test_name):
        """Custom assertion with detailed output"""
        try:
            if actual == expected:
                self.passed += 1
                self.tests.append(f"✅ PASS: {test_name}")
                print(f"✅ PASS: {test_name}")
                print(f"   Expected: {expected}")
                print(f"   Actual:   {actual}")
            else:
                self.failed += 1
                self.tests.append(f"❌ FAIL: {test_name}")
                print(f"❌ FAIL: {test_name}")
                print(f"   Expected: {expected}")
                print(f"   Actual:   {actual}")
        except Exception as e:
            self.failed += 1
            self.tests.append(f"❌ ERROR: {test_name} - {str(e)}")
            print(f"❌ ERROR: {test_name} - {str(e)}")
        print()

    def assert_contains(self, text, substring, test_name):
        """Check if text contains substring"""
        self.assert_equal(substring in text, True, f"{test_name} - contains '{substring}'")

    def assert_not_contains(self, text, substring, test_name):
        """Check if text does NOT contain substring"""
        self.assert_equal(substring in text, False, f"{test_name} - does NOT contain '{substring}'")

    def create_test_applicant(self, **kwargs):
        """Create a test applicant with default values - no database save needed for analysis"""
        import uuid
        defaults = {
            'first_name': 'Test',
            'last_name': 'User',
            'email': f'test{uuid.uuid4()}@example.com',  # Unique email
            'phone_number': '555-123-4567',
            'employment_status': 'employed',
            'evicted_before': False,
        }
        defaults.update(kwargs)
        
        # Create mock applicant
        applicant = Applicant(**defaults)
        
        # Mock the related field managers without assignment
        def mock_all():
            return []
        def mock_count():
            return 0
        def mock_exists():
            return False
        def mock_filter(**filter_kwargs):
            # Create a simple object that has the same interface
            class FilterResult:
                def exists(self):
                    return False
                def all(self):
                    return []
                def count(self):
                    return 0
            return FilterResult()
        def mock_select_related():
            class SelectRelatedResult:
                def all(self):
                    return []
            return SelectRelatedResult()
        
        # Monkey patch the managers
        if hasattr(applicant, 'jobs'):
            applicant.jobs.all = mock_all
            applicant.jobs.count = mock_count
            applicant.jobs.exists = mock_exists
            applicant.jobs.filter = mock_filter
            applicant.jobs.select_related = mock_select_related
            
        if hasattr(applicant, 'income_sources'):
            applicant.income_sources.all = mock_all
            applicant.income_sources.count = mock_count
            applicant.income_sources.exists = mock_exists
            applicant.income_sources.filter = mock_filter
            applicant.income_sources.select_related = mock_select_related
            
        if hasattr(applicant, 'previous_addresses'):
            applicant.previous_addresses.all = mock_all
            applicant.previous_addresses.count = mock_count
        
        return applicant

    def test_decimal_precision(self):
        """TEST 1: Decimal Precision for Financial Calculations"""
        print("🧪 TEST 1: DECIMAL PRECISION")
        print("=" * 50)
        
        # Create test applicant with precise income that gives exactly 3.0 ratio
        # $60000 annual = $5000 monthly, rent = $5000/3 = $1666.666... for exactly 3.0x
        applicant = self.create_test_applicant(
            annual_income=Decimal('60000'),
            max_rent_budget=Decimal('5000') / Decimal('3')  # This gives exactly 3.0x ratio
        )
        
        # Run analysis
        result = SmartInsights.analyze_applicant(applicant)
        affordability = result['affordability']
        
        # Calculate expected values
        monthly_income = Decimal('60000') / Decimal('12')  # = 5000.0
        expected_multiple = monthly_income / (Decimal('5000') / Decimal('3'))  # Should be exactly 3.0
        
        print(f"Annual Income: ${applicant.annual_income}")
        print(f"Monthly Income: ${monthly_income}")
        print(f"Rent Budget: ${applicant.max_rent_budget}")
        print(f"Expected Multiple: {expected_multiple}")
        print(f"Actual Multiple: {affordability['income_multiple']}")
        print()
        
        # Test exact calculation (should be >= 3.0 for affordability)
        self.assert_equal(
            affordability['income_multiple'] >= Decimal('3.0'), 
            True, 
            "Income multiple >= 3.0 (precise Decimal calculation)"
        )
        
        self.assert_equal(
            affordability['can_afford'], 
            True, 
            "Can afford rent with 3x income rule"
        )
        
        # Test that we're using Decimal, not float
        self.assert_equal(
            type(affordability['income_multiple']), 
            Decimal, 
            "Income multiple is Decimal type (not float)"
        )

    def test_none_vs_zero_income(self):
        """TEST 2: None vs 0 Income Handling"""
        print("🧪 TEST 2: NONE vs 0 INCOME HANDLING")
        print("=" * 50)
        
        # Test Case A: None income (missing data)
        print("Test Case A: None Income (Missing Data)")
        applicant_none = self.create_test_applicant(
            annual_income=None,
            max_rent_budget=Decimal('1500')
        )
        
        result_none = SmartInsights.analyze_applicant(applicant_none)
        affordability_none = result_none['affordability']
        
        print(f"Income: {applicant_none.annual_income}")
        print(f"Details: {affordability_none['details']}")
        print()
        
        self.assert_contains(
            affordability_none['details'],
            "No verified income information",
            "None income shows 'No verified income information'"
        )
        
        self.assert_equal(
            affordability_none['can_afford'],
            False,
            "None income cannot afford rent"
        )
        
        # Test Case B: Zero income (documented $0)
        print("Test Case B: Zero Income (Documented $0)")
        applicant_zero = self.create_test_applicant(
            annual_income=Decimal('0'),
            max_rent_budget=Decimal('1500')
        )
        
        result_zero = SmartInsights.analyze_applicant(applicant_zero)
        affordability_zero = result_zero['affordability']
        
        print(f"Income: {applicant_zero.annual_income}")
        print(f"Details: {affordability_zero['details']}")
        print()
        
        self.assert_equal(
            affordability_zero['income_multiple'],
            Decimal('0'),
            "Zero income has 0 income multiple"
        )
        
        self.assert_equal(
            affordability_zero['can_afford'],
            False,
            "Zero income cannot afford rent"
        )

    def test_fair_housing_compliance(self):
        """TEST 3: Fair Housing Compliance (Student Scoring)"""
        print("🧪 TEST 3: FAIR HOUSING COMPLIANCE (STUDENT SCORING)")
        print("=" * 50)
        
        # Test Case A: Student WITH documented income
        print("Test Case A: Student WITH Documented Income")
        student_with_income = self.create_test_applicant(
            employment_status='student',
            annual_income=Decimal('20000')
        )
        
        result_with_income = SmartInsights.analyze_applicant(student_with_income)
        employment_with_income = result_with_income['employment_stability']
        
        print(f"Employment Status: {student_with_income.employment_status}")
        print(f"Annual Income: ${student_with_income.annual_income}")
        print(f"Stability Score: {employment_with_income['stability_score']}")
        print(f"Strengths: {employment_with_income['strengths']}")
        print()
        
        self.assert_equal(
            employment_with_income['stability_score'] > 0,
            True,
            "Student with income gets stability score points"
        )
        
        student_strength_found = any("Student with documented income" in strength 
                                   for strength in employment_with_income['strengths'])
        self.assert_equal(
            student_strength_found,
            True,
            "Student with income shows 'Student with documented income'"
        )
        
        # Test Case B: Student WITHOUT income
        print("Test Case B: Student WITHOUT Income")
        student_no_income = self.create_test_applicant(
            employment_status='student',
            annual_income=None
        )
        
        result_no_income = SmartInsights.analyze_applicant(student_no_income)
        employment_no_income = result_no_income['employment_stability']
        
        print(f"Employment Status: {student_no_income.employment_status}")
        print(f"Annual Income: {student_no_income.annual_income}")
        print(f"Stability Score: {employment_no_income['stability_score']}")
        print(f"Concerns: {employment_no_income['concerns']}")
        print()
        
        verification_concern_found = any("verification required" in concern.lower() 
                                       for concern in employment_no_income['concerns'])
        self.assert_equal(
            verification_concern_found,
            True,
            "Student without income shows 'verification required'"
        )
        
        # Should not get unfair advantage over unemployed
        unemployed = self.create_test_applicant(
            employment_status='unemployed',
            annual_income=None
        )
        
        result_unemployed = SmartInsights.analyze_applicant(unemployed)
        employment_unemployed = result_unemployed['employment_stability']
        
        print(f"Student Score (no income): {employment_no_income['stability_score']}")
        print(f"Unemployed Score: {employment_unemployed['stability_score']}")
        print()
        
        # Student without income should not score higher than unemployed
        self.assert_equal(
            employment_no_income['stability_score'] <= employment_unemployed['stability_score'],
            True,
            "Student without income does not score higher than unemployed (Fair Housing)"
        )

    def test_xss_protection(self):
        """TEST 4: XSS Protection in Text Output"""
        print("🧪 TEST 4: XSS PROTECTION")
        print("=" * 50)
        
        # Create applicant with malicious eviction explanation
        malicious_input = "<script>alert('xss')</script>Previous eviction due to job loss"
        
        applicant = self.create_test_applicant(
            evicted_before=True,
            eviction_explanation=malicious_input,
            annual_income=Decimal('50000')
        )
        
        result = SmartInsights.analyze_applicant(applicant)
        rental_history = result['rental_history']
        
        print(f"Original Input: {malicious_input}")
        print(f"Concerns: {rental_history['concerns']}")
        print()
        
        # Check that script tag is escaped
        concerns_text = ' '.join(rental_history['concerns'])
        
        self.assert_contains(
            concerns_text,
            "&lt;script&gt;",
            "Script tag is HTML escaped (&lt;script&gt;)"
        )
        
        self.assert_not_contains(
            concerns_text,
            "<script>",
            "Raw script tag is NOT present"
        )
        
        self.assert_contains(
            concerns_text,
            "Previous eviction",
            "Safe content is preserved"
        )

    def run_all_tests(self):
        """Run all tests and display summary"""
        print("🧪 SMART INSIGHTS CRITICAL BUG FIX VALIDATION")
        print("=" * 60)
        print()
        
        try:
            self.test_decimal_precision()
            self.test_none_vs_zero_income()
            self.test_fair_housing_compliance()
            self.test_xss_protection()
            
        except Exception as e:
            print(f"❌ CRITICAL ERROR: {str(e)}")
            self.failed += 1
        
        print()
        print("=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        for test in self.tests:
            print(test)
        
        print()
        print(f"✅ PASSED: {self.passed}")
        print(f"❌ FAILED: {self.failed}")
        print(f"📊 TOTAL:  {self.passed + self.failed}")
        
        if self.failed == 0:
            print("\n🎉 ALL TESTS PASSED! Smart Insights is bulletproof! 🎉")
            return True
        else:
            print(f"\n⚠️  {self.failed} TEST(S) FAILED - NEEDS INVESTIGATION")
            return False


if __name__ == "__main__":
    tester = TestSmartInsights()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)