"""
Smart Insights Analysis Service
===============================

Provides rule-based analysis of applicant profiles to help brokers and admins
quickly assess applicant viability and rental affordability without needing
full documentation or credit checks.

PRIVACY & SECURITY:
- Uses local rule-based algorithms only
- NO external AI API calls (OpenAI, Anthropic, etc.)
- NO PII sent to external services
- All processing happens within your secure environment
- Follows rental industry best practices and standards

This system analyzes numerical data (income, dates, counts) and categorical
information (employment status, housing type) to generate insights while
keeping all personal information completely secure and private.
"""

import re
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.html import escape
from decimal import Decimal, InvalidOperation
import logging

logger = logging.getLogger(__name__)


class SmartInsights:
    """
    AI-powered applicant analysis service for rental application evaluation
    """
    
    @classmethod
    def analyze_applicant(cls, applicant):
        """
        Comprehensive analysis of an applicant's profile
        Returns insights about rental readiness, affordability, and risk assessment
        """
        insights = {
            'overall_score': 0,
            'affordability': cls._analyze_affordability(applicant),
            'employment_stability': cls._analyze_employment(applicant),
            'rental_history': cls._analyze_rental_history(applicant),
            'red_flags': cls._identify_red_flags(applicant),
            'recommendations': cls._generate_recommendations(applicant),
            'summary': '',
            'confidence_level': 'Medium'
        }
        
        insights['overall_score'] = cls._calculate_overall_score(insights)
        insights['confidence_level'] = cls._determine_confidence(applicant, insights)
        
        # Categorize missing fields
        missing_data = cls._get_critical_missing_fields(applicant)
        insights['missing_requirements'] = missing_data # Store full struct for debugging
        
        # Inject into specific sections for display
        insights['affordability']['missing_fields'] = missing_data['affordability']
        insights['employment_stability']['missing_fields'] = missing_data['employment_stability']
        insights['rental_history']['missing_fields'] = missing_data['rental_history']
        
        insights['summary'] = cls._generate_summary(applicant, insights)
        
        return insights
    
    @classmethod
    def _analyze_affordability(cls, applicant):
        """Analyze if applicant can afford their desired rent using Decimal precision"""
        analysis = {
            'can_afford': False,
            'recommended_rent': Decimal('0'),
            'income_multiple': Decimal('0'),
            'details': 'Insufficient income information'
        }
        
        total_monthly_income = Decimal('0')
        
        # Use Decimal arithmetic for precise money calculations
        # Handle None vs 0 income properly
        if applicant.annual_income is not None:
            try:
                annual = Decimal(str(applicant.annual_income))
                if annual > 0:  # Only add positive income
                    total_monthly_income += annual / Decimal('12')
            except (InvalidOperation, ValueError) as e:
                logger.warning(f"Invalid annual_income for applicant {applicant.id}: {applicant.annual_income}")
        
        # Use select_related to optimize database queries
        for job in applicant.jobs.select_related().all():
            if job.annual_income is not None:
                try:
                    annual = Decimal(str(job.annual_income))
                    if annual > 0:
                        total_monthly_income += annual / Decimal('12')
                except (InvalidOperation, ValueError) as e:
                    logger.warning(f"Invalid job annual_income for applicant {applicant.id}: {job.annual_income}")
        
        for income in applicant.income_sources.select_related().all():
            if income.average_annual_income is not None:
                try:
                    annual = Decimal(str(income.average_annual_income))
                    if annual > 0:
                        total_monthly_income += annual / Decimal('12')
                except (InvalidOperation, ValueError) as e:
                    logger.warning(f"Invalid income source for applicant {applicant.id}: {income.average_annual_income}")
        
        if total_monthly_income > 0:
            # Standard is 3x rent rule - using Decimal for precision
            recommended_rent = total_monthly_income / Decimal('3')
            analysis['recommended_rent'] = recommended_rent.quantize(Decimal('0.01'))
            
            if applicant.max_rent_budget is not None:
                try:
                    budget = Decimal(str(applicant.max_rent_budget))
                    # Prevent division by zero
                    if budget > 0:
                        analysis['income_multiple'] = total_monthly_income / budget
                        analysis['can_afford'] = analysis['income_multiple'] >= Decimal('3.0')
                        
                        # Safe formatting for display
                        income_fmt = float(total_monthly_income)
                        budget_fmt = float(budget)
                        multiple_fmt = float(analysis['income_multiple'])
                        
                        if analysis['can_afford']:
                            analysis['details'] = f"Strong affordability: Income of ${income_fmt:,.0f}/month supports ${budget_fmt:,.0f} rent ({multiple_fmt:.1f}x income rule)"
                        elif analysis['income_multiple'] >= Decimal('2.5'):
                            analysis['details'] = f"Borderline affordability: Income of ${income_fmt:,.0f}/month for Applicant's Max Budget of ${budget_fmt:,.0f} ({multiple_fmt:.1f}x). Consider with strong credit/references."
                        else:
                            analysis['details'] = f"Poor affordability: Income of ${income_fmt:,.0f}/month is insufficient for Applicant's Max Budget of ${budget_fmt:,.0f} ({multiple_fmt:.1f}x income rule)."
                    else:
                        analysis['details'] = "Invalid rent budget: must be greater than $0"
                except (InvalidOperation, ValueError) as e:
                    logger.warning(f"Invalid max_rent_budget for applicant {applicant.id}: {applicant.max_rent_budget}")
                    analysis['details'] = "Unable to analyze affordability: invalid rent budget"
            else:
                analysis['details'] = f"Monthly income: ${float(total_monthly_income):,.0f}. Recommended max rent: ${float(recommended_rent):,.0f} (3x income rule)"
        else:
            # Handle zero/no income explicitly
            analysis['details'] = 'No verified income information available - income verification required'
        
        return analysis
    
    @classmethod
    def _analyze_employment(cls, applicant):
        """Analyze employment stability and history"""
        analysis = {
            'stability_score': 0,
            'employment_length': 'Unknown',
            'job_count': 0,
            'concerns': [],
            'strengths': []
        }
        
        # Count total jobs
        job_count = 1 if applicant.company_name else 0
        job_count += applicant.jobs.count()
        analysis['job_count'] = job_count
        
        # Analyze primary employment
        if applicant.employment_start_date:
            employment_duration = (timezone.now().date() - applicant.employment_start_date).days
            years = employment_duration / 365.25
            analysis['employment_length'] = f"{years:.1f} years" if years >= 1 else f"{employment_duration} days"
            
            if years >= 2:
                analysis['stability_score'] += 30
                analysis['strengths'].append(f"Stable primary employment ({years:.1f} years)")
            elif years >= 1:
                analysis['stability_score'] += 20
                analysis['strengths'].append(f"Good employment duration ({years:.1f} years)")
            else:
                analysis['concerns'].append(f"Short employment history ({employment_duration} days)")
        
        # Employment status analysis - Fair Housing compliant scoring
        # Remove discriminatory assumptions about students
        if applicant.employment_status == 'employed':
            analysis['stability_score'] += 25
            analysis['strengths'].append("Currently employed")
        elif applicant.employment_status == 'student':
            # Fair Housing compliance: Base scoring on verifiable income, not assumptions
            # Students are scored based on documented income sources, not assumptions about family support
            has_income = (applicant.annual_income and applicant.annual_income > 0) or \
                        applicant.jobs.filter(annual_income__gt=0).exists() or \
                        applicant.income_sources.filter(average_annual_income__gt=0).exists()
            
            if has_income:
                analysis['stability_score'] += 15
                analysis['strengths'].append("Student with documented income")
            else:
                analysis['concerns'].append("Student status with no documented income - verification required")
        elif applicant.employment_status == 'unemployed':
            analysis['concerns'].append("Currently unemployed")
        elif applicant.employment_status == 'self_employed':
            analysis['stability_score'] += 10
            analysis['concerns'].append("Self-employed (variable income)")
        
        # Multiple jobs analysis
        if job_count > 1:
            analysis['strengths'].append(f"Multiple income sources ({job_count} jobs)")
            analysis['stability_score'] += 10
        elif job_count == 0:
            # Check if income exists even if jobs don't (Stated Income case)
            has_income = (applicant.annual_income and applicant.annual_income > 0)
            if not has_income:
                analysis['concerns'].append("No employment information provided")
            else:
                 # Income exists but no employment details - relied on missing_fields list to warn user
                 # Adding a specific concern for clarity
                 analysis['concerns'].append("Income stated without verified employment source")
        
        return analysis
    
    @classmethod
    def _analyze_rental_history(cls, applicant):
        """Analyze rental and housing history"""
        analysis = {
            'history_score': 0,
            'concerns': [],
            'strengths': [],
            'address_count': 0
        }
        
        # Current address analysis - use new structured fields
        total_months = 0
        if applicant.current_address_years:
            total_months += applicant.current_address_years * 12
        if applicant.current_address_months:
            total_months += applicant.current_address_months
            
        if total_months > 0:
            duration_display = applicant.current_address_duration_display
            if total_months >= 24:  # 2+ years
                analysis['history_score'] += 20
                analysis['strengths'].append(f"Stable at current address ({duration_display})")
            elif total_months >= 12:  # 1+ year
                analysis['history_score'] += 15
                analysis['strengths'].append(f"Good stability at current address ({duration_display})")
            elif total_months >= 6:  # 6+ months
                analysis['history_score'] += 5
                analysis['strengths'].append(f"Some stability at current address ({duration_display})")
            else:
                analysis['concerns'].append(f"Short duration at current address ({duration_display})")
                analysis['concerns'].append(f"Short duration at current address ({applicant.length_at_current_address})")
        
        # Total Housing History (5-Year Rule) is calculated here
        total_history_months = cls._calculate_total_housing_history_months(applicant)
        if total_history_months >= 60:
            analysis['history_score'] += 10
            years_fmt = total_history_months / 12
            analysis['strengths'].append(f"5+ Years Housing History Verified ({years_fmt:.1f} years)")
        elif total_history_months >= 36:
            analysis['history_score'] += 5
            years_fmt = total_history_months / 12
            analysis['strengths'].append(f"Good Housing History ({years_fmt:.1f} years)")
        else:
            years_fmt = total_history_months / 12
            analysis['concerns'].append(f"Limited Housing History Verified ({years_fmt:.1f} years)")
        
        # Housing status
        if applicant.housing_status == 'rent':
            analysis['history_score'] += 15
            analysis['strengths'].append("Current renter (understands rental obligations)")
        elif applicant.housing_status == 'own':
            analysis['history_score'] += 10
            analysis['strengths'].append("Current homeowner")
        elif applicant.housing_status == 'family':
            analysis['concerns'].append("Living with family (limited rental experience)")
        
        # Previous addresses
        prev_count = applicant.previous_addresses.count()
        analysis['address_count'] = prev_count
        if prev_count > 3:
            analysis['concerns'].append(f"Frequent moves ({prev_count} previous addresses)")
        elif prev_count == 0:
            analysis['concerns'].append("No previous address history provided")
        
        # Landlord references
        if applicant.current_landlord_name:
            analysis['history_score'] += 15
            analysis['strengths'].append("Landlord reference available")
        
        # Eviction history
        if applicant.evicted_before:
            analysis['concerns'].append("Previous eviction reported")
            if applicant.eviction_explanation:
                # Sanitize text input to prevent XSS
                sanitized_explanation = escape(applicant.eviction_explanation.strip())
                analysis['concerns'].append(f"Explanation: {sanitized_explanation[:100]}...")
        else:
            analysis['history_score'] += 10
            analysis['strengths'].append("No eviction history reported")
        
        return analysis
    
    @classmethod
    def _identify_red_flags(cls, applicant):
        """Identify potential red flags in the application"""
        red_flags = []
        
        # Income vs budget mismatch - use Decimal for precision
        if applicant.annual_income and applicant.max_rent_budget:
            try:
                monthly_income = Decimal(str(applicant.annual_income)) / Decimal('12')
                max_budget = Decimal(str(applicant.max_rent_budget))
                if max_budget > monthly_income / Decimal('2'):
                    red_flags.append("🚩 Rent budget exceeds 50% of reported income")
            except (InvalidOperation, ValueError):
                red_flags.append("⚠️ Invalid income or budget data")
        
        # Missing critical information
        missing_info = []
        if not applicant.phone_number:
            missing_info.append("phone number")
        if not applicant.email:
            missing_info.append("email")
        if not applicant.annual_income and not applicant.jobs.exists():
            missing_info.append("income information")
        
        if missing_info:
            red_flags.append(f"⚠️ Missing: {', '.join(missing_info)}")
        
        # Employment concerns
        if applicant.employment_status == 'unemployed':
            red_flags.append("🚩 Currently unemployed")
        
        # Unrealistic expectations
        if applicant.max_rent_budget and applicant.max_rent_budget < 500:
            red_flags.append("⚠️ Very low rent budget may indicate unrealistic expectations")
        
        # Eviction history
        if applicant.evicted_before:
            red_flags.append("🚩 Previous eviction history")
        
        return red_flags
    
    @classmethod
    def _generate_recommendations(cls, applicant):
        """Generate recommendations for brokers"""
        recommendations = []
        
        # Income verification
        if applicant.annual_income:
            recommendations.append("📋 Request recent pay stubs to verify reported income")
        
        # Employment verification
        if applicant.company_name and applicant.supervisor_name:
            recommendations.append("📞 Contact supervisor for employment verification")
        
        # References
        if applicant.current_landlord_name:
            recommendations.append("🏠 Contact current landlord for rental reference")
        
        # Credit check
        recommendations.append("💳 Run credit check to verify financial responsibility")
        
        # Bank statements - use Decimal for precision
        if applicant.annual_income:
            try:
                annual_income = Decimal(str(applicant.annual_income))
                if annual_income > Decimal('50000'):
                    recommendations.append("🏦 Request bank statements for income verification")
            except (InvalidOperation, ValueError):
                pass  # Skip recommendation if income is invalid
        
        # Emergency contact verification
        if applicant.emergency_contact_name:
            recommendations.append("👥 Verify emergency contact information")
        
        return recommendations
    
    @classmethod
    def _calculate_overall_score(cls, insights):
        """Calculate overall applicant score out of 100"""
        score = 0
        
        # Affordability (40% weight) - handle Decimal values
        if insights['affordability']['can_afford']:
            score += 40
        elif insights['affordability']['income_multiple'] >= Decimal('2.5'):
            score += 25
        elif insights['affordability']['income_multiple'] >= Decimal('2.0'):
            score += 15
        
        # Employment stability (30% weight)
        employment_score = insights['employment_stability']['stability_score']
        score += min(employment_score * 0.3, 30)
        
        # Rental history (20% weight)
        history_score = insights['rental_history']['history_score']
        score += min(history_score * 0.4, 20)
        
        # Red flags penalty (10% weight)
        red_flag_count = len(insights['red_flags'])
        score -= red_flag_count * 2
        
        return max(0, min(100, round(score)))
    
    @classmethod
    def _generate_summary(cls, applicant, insights):
        """Generate AI-like summary of the applicant"""
        score = insights['overall_score']
        affordability = insights['affordability']
        confidence = insights.get('confidence_level', 'Medium')
        
        # Check if there are significant missing fields across sections
        missing_affordability = insights['affordability'].get('missing_fields', [])
        missing_employment = insights['employment_stability'].get('missing_fields', [])
        missing_housing = insights['rental_history'].get('missing_fields', [])
        total_missing = len(missing_affordability) + len(missing_employment) + len(missing_housing)
        
        # Scenario: Low Score primarily due to missing data (Low Confidence)
        if confidence == 'Low' and score < 50 and total_missing > 0:
            risk_level = "UNABLE TO ASSESS"
            recommendation = "INSUFFICIENT DATA"
            summary = f"**{recommendation}** - Score is limited by missing information. Please review the specific sections below for details."
            return summary

        # Standard Scenarios
        if score >= 80:
            risk_level = "LOW RISK"
            recommendation = "HIGHLY RECOMMENDED"
        elif score >= 60:
            risk_level = "MEDIUM RISK"
            recommendation = "RECOMMENDED WITH VERIFICATION"
        elif score >= 40:
            risk_level = "HIGH RISK"
            recommendation = "PROCEED WITH CAUTION"
        else:
            risk_level = "VERY HIGH RISK"
            recommendation = "NOT RECOMMENDED"
        
        summary = f"**{recommendation}** ({risk_level}) - "
        
        if affordability['can_afford']:
            summary += f"Strong financial profile with {float(affordability['income_multiple']):.1f}x income coverage. "
        elif affordability['income_multiple'] >= Decimal('2.5'):
            summary += f"Adequate income with {float(affordability['income_multiple']):.1f}x coverage, consider with good credit. "
        elif affordability['income_multiple'] > 0:
            summary += f"Income concerns with only {float(affordability['income_multiple']):.1f}x coverage. "
        else:
            summary += "No income information available for analysis. "
        
        employment = insights['employment_stability']
        if employment['strengths']:
            # Sanitize text before displaying
            sanitized_strength = escape(str(employment['strengths'][0]))
            summary += f"Employment: {sanitized_strength}. "
        elif missing_employment:
             summary += f"Missing critical employment data. "
        
        if insights['red_flags']:
            summary += f"⚠️ {len(insights['red_flags'])} concern(s) identified."
        else:
            summary += "No major red flags detected."
        
        return summary
    
    @classmethod
    def _determine_confidence(cls, applicant, insights):
        """Determine confidence level in the analysis"""
        data_completeness = 0
        
        # Check data completeness
        if applicant.annual_income:
            data_completeness += 25
        if applicant.employment_start_date:
            data_completeness += 20
        if applicant.current_landlord_name:
            data_completeness += 15
        if applicant.length_at_current_address:
            data_completeness += 15
        if applicant.previous_addresses.count() > 0:
            data_completeness += 10
        if applicant.jobs.count() > 0:
            data_completeness += 10
        if applicant.emergency_contact_name:
            data_completeness += 5
        
        if data_completeness >= 80:
            return "High"
        elif data_completeness >= 50:
            return "Medium"
        else:
            return "Low"

    @classmethod
    def _calculate_total_housing_history_months(cls, applicant):
        """Calculate total months of housing history provided"""
        total_months = 0
        
        # Current Address
        if applicant.current_address_years:
            total_months += applicant.current_address_years * 12
        if applicant.current_address_months:
            total_months += applicant.current_address_months
            
        # Previous Addresses
        for addr in applicant.previous_addresses.all():
            if addr.years:
                total_months += addr.years * 12
            if addr.months:
                total_months += addr.months
                
        return total_months

    @staticmethod
    def _is_field_filled(value):
        """Helper to check if a field value is considered 'filled' for AI purposes"""
        if value is None:
            return False
        if isinstance(value, str) and not value.strip():
            return False
        if isinstance(value, (int, float, Decimal)) and value <= 0:
            # For financial fields, 0 or negative is considered 'unfilled' for matching
            return False
        return True

    @classmethod
    def _get_critical_missing_fields(cls, applicant):
        """Identify critical missing fields categorized by section.
        
        This method directly inspects Applicant fields to ensure Smart Insights 
        remains accurate even if the UI Profile Completion steps aren't finished.
        """
        categorized_missing = {
            'affordability': [],
            'employment_stability': [],
            'rental_history': []
        }
        
        # 1. Affordability Check
        if not cls._is_field_filled(applicant.annual_income):
            # Check if they have jobs even if annual_income (cached) isn't set
            if not applicant.jobs.exists():
                categorized_missing['affordability'].append("Annual Income")
        
        if not cls._is_field_filled(applicant.max_rent_budget):
            categorized_missing['affordability'].append("Max Rent Budget")

        # 2. Employment Stability Check
        if not cls._is_field_filled(applicant.employment_status):
            categorized_missing['employment_stability'].append("Employment Status")
        
        if not applicant.jobs.exists():
            categorized_missing['employment_stability'].append("Current Employer Info")

        # 3. Rental History Check
        if not cls._is_field_filled(applicant.street_address_1):
            categorized_missing['rental_history'].append("Current Street Address")
        
        if not cls._is_field_filled(applicant.city):
            categorized_missing['rental_history'].append("Current City")
            
        if not cls._is_field_filled(applicant.zip_code):
            categorized_missing['rental_history'].append("Current Zip Code")

        if not cls._is_field_filled(applicant.current_landlord_name):
            categorized_missing['rental_history'].append("Current Landlord Name")

        if not applicant.previous_addresses.exists():
            categorized_missing['rental_history'].append("Previous Address History")
                    
        return categorized_missing