# Test vs Implementation Mapping Document
Generated: 2025-11-14

## Overview
This document maps the differences between test expectations and actual model/method implementations in the applicants app.

## 1. Model Field Mappings

### Applicant Model
| Test Expects | Actual Field | Type | Notes |
|--------------|--------------|------|-------|
| `phone` | `phone_number` | CharField | ✅ Fixed |
| `current_address` | `street_address_1` | CharField | ✅ Fixed |
| `budget_max` | `max_rent_budget` | DecimalField | ✅ Fixed |
| `budget_min` | Does not exist | - | Tests should use only max |
| `desired_bedrooms_min` | `min_bedrooms` | CharField | ✅ Fixed |
| `desired_bedrooms_max` | `max_bedrooms` | CharField | ✅ Fixed |
| `desired_bathrooms_min` | `min_bathrooms` | CharField | ✅ Fixed |
| `desired_bathrooms_max` | `max_bathrooms` | CharField | ✅ Fixed |

### ApplicantJob Model
| Test Expects | Actual Field | Type | Notes |
|--------------|--------------|------|-------|
| `is_current` | `currently_employed` | BooleanField | ✅ Fixed |
| `start_date` | `employment_start_date` | DateField | ✅ Fixed |

### ApplicantIncomeSource Model
| Test Expects | Actual Field | Type | Notes |
|--------------|--------------|------|-------|
| `monthly_amount` | `average_annual_income` | DecimalField | ❌ Need to fix - different units |
| `description` | `income_source` | CharField | ❌ Need to fix |
| `source_type` param in test | `source_type` exists | CharField | ✅ Correct |

### Building Model (from buildings app)
| Test Expects | Actual Field | Type | Notes |
|--------------|--------------|------|-------|
| `address` | `street_address_1` | CharField | ❌ Need to fix |
| `city` | `city` | CharField | ✅ Correct |
| `state` | `state` | CharField | ✅ Correct |
| `zip_code` | `zip_code` | CharField | ✅ Correct |

### ApplicantActivity Model
| Test Expects | Actual Field | Type | Notes |
|--------------|--------------|------|-------|
| `ACTIVITY_CHOICES` | `ACTIVITY_TYPES` | List of tuples | ✅ Fixed |

## 2. Method/Function Mappings

### ActivityTracker Class
| Test Expects | Actual Method | Notes |
|--------------|---------------|-------|
| `log_activity()` | `track_activity()` | ✅ Fixed |
| `get_activity_summary()` | `get_activity_summary()` | ✅ Correct |

### SmartInsights.analyze_applicant() Response
| Test Expects | Actual Returns | Notes |
|--------------|----------------|-------|
| `affordability['income_to_rent_ratio']` | `affordability['income_multiple']` | ❌ Different key name (3.33x vs 40x) |
| `affordability['meets_40x_rule']` | Not provided | ❌ Missing - could derive from `can_afford` |
| `employment_stability['is_stable']` | Not provided | ❌ Has `stability_score` instead |
| `employment_stability['current_job_tenure_months']` | Not provided | ❌ Has `employment_length` as string |
| `red_flags` (list of strings) | `red_flags` (list of strings) | ✅ Correct type |
| `red_flags` contains 'no_income' | Actual: '⚠️ Missing: phone number' | ❌ Different flag format |
| `red_flags` contains 'short_residence_history' | Unknown | ❌ Need to test |

### Applicant Model Methods
| Test Expects | Actual Implementation | Notes |
|--------------|----------------------|-------|
| `calculate_total_income()` | ✅ Implemented | Uses `currently_employed` for jobs |
| `get_profile_completion_score()` | ✅ Implemented | Uses actual field names |

## 3. Authentication Issues

### User Login (Django auth)
| Test Uses | Should Use | Notes |
|-----------|------------|-------|
| `self.client.login(username=...)` | `self.client.login(email=...)` | ✅ Fixed |
| User.objects.create_user(username=...) | User.objects.create_user(email=...) | ✅ Fixed |

## 4. Test Failures Analysis

### ERROR Tests (8 total)
1. **test_matching_algorithm_accuracy** - Building `address` field issue
2. **test_budget_tolerance** - Building `address` field issue  
3. **test_amenity_preference_scoring** - Building `address` field issue
4. **test_apartment_matching_performance** - Building `address` field issue
5. **test_total_income_calculation** - ApplicantIncomeSource field issues
6. **test_dashboard_access_control** - Likely authentication issue
7. **test_activity_filtering** - Likely authentication issue
8. **test_employment_stability_scoring** - SmartInsights structure issue

### FAIL Tests (4 total)
1. **test_profile_completion_score** - Logic expects different score calculation
2. **test_activity_summary_generation** - Count mismatch (expects 5, gets different)
3. **test_affordability_analysis** - SmartInsights keys don't match
4. **test_red_flag_detection** - SmartInsights implementation differs

## 5. Required Fixes

### Priority 1: Quick Fixes (Field Renames)
- [ ] Fix ApplicantIncomeSource test fields
- [ ] Fix Building model field references
- [ ] Update SmartInsights test assertions

### Priority 2: Logic Fixes
- [ ] Align SmartInsights response structure
- [ ] Fix activity count calculation
- [ ] Update profile completion score logic

### Priority 3: Implementation Decisions
- [ ] Decide if tests should match implementation or vice versa
- [ ] Determine if SmartInsights needs `meets_40x_rule` field
- [ ] Confirm authentication flow for dashboard tests

## 6. Income Calculation Discrepancy

### Test Expectation
```python
ApplicantIncomeSource.objects.create(
    monthly_amount=2000  # $24k annually
)
```

### Actual Model
```python
ApplicantIncomeSource.objects.create(
    average_annual_income=24000  # Direct annual amount
)
```

**Impact**: The `calculate_total_income()` method expects `monthly_amount` but model has `average_annual_income`

## 7. Recommendations

1. **Option A: Fix Tests to Match Implementation**
   - Pros: Faster, tests reflect reality
   - Cons: May test wrong business logic

2. **Option B: Fix Implementation to Match Tests**
   - Pros: Tests define expected behavior
   - Cons: May break existing functionality

3. **Option C: Hybrid Approach** ✅ Recommended
   - Fix obvious field name mismatches in tests
   - Add missing SmartInsights fields if business-critical
   - Document why certain differences exist

## 8. Next Steps

1. Review this mapping with stakeholders
2. Decide on approach (A, B, or C)
3. Create tickets for each fix
4. Implement fixes in priority order
5. Run full test suite after each category of fixes

## 9. Actual Response Examples

### SmartInsights Affordability Response
```python
{
    'can_afford': True,
    'recommended_rent': 3333.33,
    'income_multiple': 3.333,  # Monthly income to rent ratio
    'details': 'Strong affordability: Income of $10,000/month...'
}
```

### SmartInsights Employment Stability Response
```python
{
    'stability_score': 0,
    'employment_length': 'Unknown',
    'job_count': 1,
    'concerns': [],
    'strengths': []
}
```

### SmartInsights Red Flags Response
```python
['⚠️ Missing: phone number', '⚠️ Missing: date of birth']
```

## Notes
- Total test count: 19
- Currently passing: 7
- Currently failing: 12 (8 errors, 4 failures)
- Target: 100% pass rate
- SmartInsights uses monthly income ratio (3.33x) not annual (40x)
- Red flags use emoji prefixes and different text format