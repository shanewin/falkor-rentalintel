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
from decimal import Decimal


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
        
        # Calculate overall score
        insights['overall_score'] = cls._calculate_overall_score(insights)
        
        # Generate summary
        insights['summary'] = cls._generate_summary(applicant, insights)
        
        # Set confidence level
        insights['confidence_level'] = cls._determine_confidence(applicant, insights)
        
        return insights
    
    @classmethod
    def _analyze_affordability(cls, applicant):
        """Analyze if applicant can afford their desired rent"""
        analysis = {
            'can_afford': False,
            'recommended_rent': 0,
            'income_multiple': 0,
            'details': 'Insufficient income information'
        }
        
        # Calculate total income
        total_monthly_income = 0
        
        # Primary employment income
        if applicant.annual_income:
            total_monthly_income += float(applicant.annual_income) / 12
        
        # Additional jobs
        for job in applicant.jobs.all():
            if job.annual_income:
                total_monthly_income += float(job.annual_income) / 12
        
        # Additional income sources
        for income in applicant.income_sources.all():
            if income.average_annual_income:
                total_monthly_income += float(income.average_annual_income) / 12
        
        if total_monthly_income > 0:
            # Standard is 3x rent rule
            recommended_rent = total_monthly_income / 3
            analysis['recommended_rent'] = round(recommended_rent, 2)
            
            if applicant.max_rent_budget:
                budget = float(applicant.max_rent_budget)
                analysis['income_multiple'] = total_monthly_income / budget if budget > 0 else 0
                analysis['can_afford'] = analysis['income_multiple'] >= 3.0
                
                if analysis['can_afford']:
                    analysis['details'] = f"Strong affordability: Income of ${total_monthly_income:,.0f}/month supports ${budget:,.0f} rent (${analysis['income_multiple']:.1f}x income rule)"
                elif analysis['income_multiple'] >= 2.5:
                    analysis['details'] = f"Borderline affordability: Income of ${total_monthly_income:,.0f}/month for ${budget:,.0f} rent ({analysis['income_multiple']:.1f}x). Consider with strong credit/references."
                else:
                    analysis['details'] = f"Poor affordability: Income of ${total_monthly_income:,.0f}/month insufficient for ${budget:,.0f} rent ({analysis['income_multiple']:.1f}x income rule)"
            else:
                analysis['details'] = f"Monthly income: ${total_monthly_income:,.0f}. Recommended max rent: ${recommended_rent:,.0f} (3x income rule)"
        
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
        
        # Employment status analysis
        if applicant.employment_status == 'employed':
            analysis['stability_score'] += 25
            analysis['strengths'].append("Currently employed")
        elif applicant.employment_status == 'student':
            analysis['stability_score'] += 15
            analysis['strengths'].append("Student status (may have family support)")
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
            analysis['concerns'].append("No employment information provided")
        
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
        
        # Current address analysis
        if applicant.length_at_current_address:
            duration = applicant.length_at_current_address.lower()
            if any(word in duration for word in ['year', 'years']) and not any(word in duration for word in ['month', '<', 'less']):
                analysis['history_score'] += 20
                analysis['strengths'].append(f"Stable at current address ({applicant.length_at_current_address})")
            else:
                analysis['concerns'].append(f"Short duration at current address ({applicant.length_at_current_address})")
        
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
                analysis['concerns'].append(f"Explanation: {applicant.eviction_explanation[:100]}...")
        else:
            analysis['history_score'] += 10
            analysis['strengths'].append("No eviction history reported")
        
        return analysis
    
    @classmethod
    def _identify_red_flags(cls, applicant):
        """Identify potential red flags in the application"""
        red_flags = []
        
        # Income vs budget mismatch
        if applicant.annual_income and applicant.max_rent_budget:
            monthly_income = float(applicant.annual_income) / 12
            if float(applicant.max_rent_budget) > monthly_income / 2:
                red_flags.append("🚩 Rent budget exceeds 50% of reported income")
        
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
        
        # Bank statements
        if applicant.annual_income and float(applicant.annual_income) > 50000:
            recommendations.append("🏦 Request bank statements for income verification")
        
        # Emergency contact verification
        if applicant.emergency_contact_name:
            recommendations.append("👥 Verify emergency contact information")
        
        return recommendations
    
    @classmethod
    def _calculate_overall_score(cls, insights):
        """Calculate overall applicant score out of 100"""
        score = 0
        
        # Affordability (40% weight)
        if insights['affordability']['can_afford']:
            score += 40
        elif insights['affordability']['income_multiple'] >= 2.5:
            score += 25
        elif insights['affordability']['income_multiple'] >= 2.0:
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
            summary += f"Strong financial profile with {affordability['income_multiple']:.1f}x income coverage. "
        elif affordability['income_multiple'] >= 2.5:
            summary += f"Adequate income with {affordability['income_multiple']:.1f}x coverage, consider with good credit. "
        else:
            summary += f"Income concerns with only {affordability['income_multiple']:.1f}x coverage. "
        
        employment = insights['employment_stability']
        if employment['strengths']:
            summary += f"Employment: {employment['strengths'][0]}. "
        
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