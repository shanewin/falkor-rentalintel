# User Data Points & Form Fields Documentation

This document outlines all data points collected from applicants during the account creation and progressive profile building process. It identifies which fields are critical for the **Smart Matching Algorithm** and which are enhancing factors.

## 1. Account Registration (Entry Point)
*Collected via `users/views.py` and `users/forms.py` (ApplicantRegistrationWithSMSForm)*

| Field Name | Type | Requirement | Notes | Algorithm Relevance |
|------------|------|-------------|-------|---------------------|
| `email` | Email | **Required** | Verified via email code. | Unique Identifier |
| `password` | Password | **Required** | Min 8 chars. | Security only |
| `first_name` | Text | **Required** | | Personalization |
| `last_name` | Text | **Required** | | Personalization |
| `phone_number` | Text | Optional | Required if SMS opt-in is checked. | Contact |
| `sms_opt_in` | Boolean | Optional | | Notification preference |
| `tcpa_consent` | Boolean | Cond. Required | Required if SMS opt-in is true. | Compliance |

---

## 2. Progressive Profile - Step 1: Basic Information
*Collected via `applicants/profile_views.py` (profile_step1) and `ApplicantBasicInfoForm`*

### Identity & Contact
| Field Name | Type | Requirement | Algorithm Relevance |
|------------|------|-------------|---------------------|
| `profile_photo` | Image | Optional | Trust factor for landlords (Soft Match) |
| `date_of_birth` | Date | Optional | Age verification (exclude <18) |
| `current_address` | Composite | Optional | Address history verification |
| `emergency_contact`| Composite | Optional | Trust/Completeness score |

### Housing History (Risk Assessment)
| Field Name | Type | Notes | Algorithm Relevance |
|------------|------|-------|---------------------|
| `housing_status` | Selection | Own/Rent/Other. If Rent -> Landlord info required. | Stability Score |
| `evicted_before` | Boolean | If Yes -> `eviction_explanation` required. | **Critical Risk Factor** |
| `reason_for_moving`| Text | | Qualitative match insight |
| `previous_addresses`| Dynamic | List of past addresses + landlord info. | Background Check Readiness |

---

## 3. Progressive Profile - Step 2: Housing Needs (The Matching Core)
*Collected via `applicants/profile_views.py` (profile_step2) and `ApplicantHousingForm`*

These fields are the primary drivers for the `matching_apartments.py` algorithm.

### Critical Matching Criteria (Hard Filters)
| Field Name | Type | Logic | Impact |
|------------|------|-------|--------|
| `desired_move_in_date` | Date | **Required** | Filters out apartments not available by this date. |
| `max_rent_budget` | Currency | **Required** | Filters out apartments costing > budget. |
| `min_bedrooms` | Int | Optional (0=Any) | Filters out apartments with fewer bedrooms. |
| `max_bedrooms` | Int | Optional | Filters out apartments with more bedrooms (efficiency). |
| `has_pets` | Boolean | Default False | If True, filters out "No Pets" buildings. |
| `pet_type` | List | Dynamic | Dog/Cat specifics may trigger weight/breed restrictions. |

### Weighted Matching Criteria (Soft Filters/Scoring)
| Field Name | Type | Logic | Impact |
|------------|------|-------|--------|
| `open_to_roommates` | Boolean | Default False | Unlocks larger units split by room/price. |
| `neighborhood_preferences` | Ranked List | Ordered 1..N | **High Weight**. Apartments in ranked neighborhoods get score boosters based on rank. |
| `building_amenities` | Rated 0-3 | 0=Don't Care, 1=Nice, 2=Imp, 3=Must | **Score Booster**. "Must Have" (3) acts as a hard filter or massive penalty if missing. |
| `apartment_amenities` | Rated 0-3 | Same as above | **Score Booster**. Granular matching (e.g., In-unit Laundry). |

---

## 4. Progressive Profile - Step 3: Financial & Employment
*Collected via `applicants/profile_views.py` (profile_step3) and `ApplicantEmploymentForm`*

Used primarily for **Income-to-Rent Ratio** calculations (Financial Qualification).

### Income Qualification (The "40x Rule")
| Field Name | Type | Requirement | Algorithm Relevance |
|------------|------|-------------|---------------------|
| `employment_status` | Selection | Student/Employed/Other | Determines income verification path. |
| `annual_income` | Currency | | **Critical**. Used to calculate `Max Affordability` (Income / 40). |
| `additional_income` | Dynamic | List of extra income sources. | Adds to total annual income. |
| `assets` | Dynamic | Liquid assets. | Can offset low income in some algorithms. |
| `guarantor` | Bool (Implicit)| *Future Field* | If income < 40x rent, checking for guarantor availability is key. |

### Employment Stability
| Field Name | Type | Notes | Algorithm Relevance |
|------------|------|-------|---------------------|
| `company_name` | Text | | Employment verification. |
| `position` | Text | | Trust score. |
| `duration` | Date Range | Start/End dates. | Job stability score. |

---

## Summary for Matching Algorithm

To feed `matching_apartments.py` effectively, we need to prioritize:

1.  **Availability**: `desired_move_in_date` vs Apartment Available Date.
2.  **Affordability**: `max_rent_budget` vs Apartment Rent (Hard Cap) AND `Total Income / 40` vs Rent (Qualification Cap).
3.  **Space**: `min_bedrooms` / `min_bathrooms`.
4.  **Policy**: `has_pets` vs Building Pet Policy.
5.  **Location**: `neighborhood_preferences` (Weighted scoring).
6.  **Lifestyle**: `amenity_preferences` (Weighted scoring).

**Recommendation**: Ensure `annual_income` is treated as a critical "Qualification" filter, distinct from the user's self-reported `max_rent_budget`. A user might *want* to spend $5k but only *qualify* for $3k.
