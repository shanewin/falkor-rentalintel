# Smart Insights Algorithm

## Overview
**Smart Insights** is a rule-based analysis service designed to help brokers and administrators quickly assess applicant viability and rental affordability. It differs from the **Smart Matching** algorithm (which finds apartments for applicants) by focusing exclusively on the financial and stability profile of the applicant themselves.

The system analyzes numerical data (income, dates, counts) and categorical information (employment status, housing type) to generate an objective risk profile without requiring full documentation or credit checks in the initial phase.

---

## Privacy & Security
The Smart Insights algorithm is built with a "Privacy First" approach:
- **Local Processing**: All calculations and logic are executed within the local environment.
- **No External AI**: The system does NOT make calls to external LLM APIs (OpenAI, Anthropic, etc.).
- **Data Security**: Non-PII (Personally Identifiable Information) data is used for scoring, and no sensitive data is sent outside the secure server.
- **Fair Housing Compliance**: Scoring logic is designed to be objective and avoid discriminatory assumptions (e.g., student status is evaluated based on documented income rather than traditional bias).

---

## Core Analysis Components

### 1. Affordability Analysis (40% Weight)
The algorithm uses **Decimal precision** for all financial calculations to ensure accuracy in currency handling. It follows the industry-standard **3x Rent Rule**.

- **Income Multiple**: Calculated as `Total Monthly Income / Max Rent Budget`.
- **Logic**:
    - **Strong Affordability (>= 3.0x)**: Income supports the requested rent.
    - **Borderline Affordability (2.5x - 3.0x)**: Potentially viable with strong credit or references.
    - **Poor Affordability (< 2.5x)**: High financial risk; income is insufficient for the budget.
- **Recommended Rent**: The system suggests a "Safe" rent amount calculated as `Total Monthly Income / 3`.

### 2. Employment Stability (30% Weight)
Evaluates the longevity and reliability of income sources.

- **Duration Points**:
    - **2+ Years**: 30 points (High Stability)
    - **1-2 Years**: 20 points (Good Stability)
    - **< 1 Year**: 0 points (Potential Concern)
- **Status Scoring**:
    - **Employed**: +25 points
    - **Student (with Income)**: +15 points (Objective verification)
    - **Self-Employed**: +10 points (Variable income consideration)
    - **Unemployed**: 0 points
- **Multi-Source Bonus**: +10 points if the applicant has multiple verified jobs/income sources.

### 3. Rental & Housing History (20% Weight)
Assesses the applicant's record as a tenant or homeowner.

- **Current Address Stability**:
    - **2+ Years**: 20 points
    - **1 Year**: 15 points
    - **6 Months**: 5 points
- **Total Housing History (5-Year Goal)**:
    - Logic sums `Current Address Duration` + all verified `Previous Address Durations`.
    - **5+ Years**: +10 points (Verified History)
    - **3-5 Years**: +5 points (Good History)
    - **< 3 Years**: 0 points (Limited History)
- **Housing Type**:
    - **Current Renter**: +15 points (Demonstrated ability to follow rental obligations)
    - **Homeowner**: +10 points
    - **Living with Family**: 0 points (Limited rental footprint)
- **Verification**: +15 points if a landlord reference is provided.

### 4. Red Flag Detection
The system identifies "🚩" (Critical) and "⚠️" (Warning) indicators:
- **Rent/Income Mismatch**: Rent budget > 50% of income.
- **Missing Data**: Lack of phone, email, or verified income.
- **Eviction History**: Previous evictions reported (includes automated sanitization of explanations to prevent XSS).
- **Unrealistic Budget**: Rent budgets below $500 for the market.

---

## Data Mapping: Form Fields to Insights

The following table maps specific fields from the Applicant Profile to the insights and scoring they influence.

| Insight Component | Source Form Field(s) | Usage in Algorithm |
| :--- | :--- | :--- |
| **Affordability** | `annual_income` | Primary monthly income calculation. |
| | `max_rent_budget` | Denominator for the 3x rent ratio check. |
| | `ApplicantJob.annual_income` | Added to total verifiable monthly income. |
| | `ApplicantIncomeSource.average_annual_income` | Added to total verifiable monthly income. |
| **Employment** | `employment_status` | Categorical scoring (Employed, Student, etc.). |
| | `employment_start_date` | Calculates tenure for stability points. |
| | `company_name` | Identifies primary employment. |
| | `ApplicantJob.count()` | Grants bonus for multiple income streams. |
| **Rental History** | `housing_status` | Scoring based on rental vs. homeownership experience. |
| | `current_address_years/months` | Measures geographic stability. |
| | `previous_addresses` (`years`, `months`) | contributes to Total Housing History calculation (sum of all durations). |
| | `previous_addresses.count()` | Identifies frequent moves or lack of history. |
| | `current_landlord_name` | Triggers "Reference Available" bonus. |
| **Risk Detection** | `evicted_before` | Critical "🚩" Red Flag if true. |
| | `eviction_explanation` | Sanitized text used in broker concern list. |
| | `phone_number` / `email` | Checks for profile completeness. |
| | `emergency_contact_name` | Influences analysis confidence level. |

---

## Overall Scoring & Risk Levels
The final score (0-100) is a weighted sum of the components above, minus a penalty for red flags (-2 points per flag).

| Score | Risk Level | Recommendation |
| :--- | :--- | :--- |
| **80 - 100** | **LOW RISK** | High Recommended |
| **60 - 79** | **MEDIUM RISK** | Recommended with Verification |
| **40 - 59** | **HIGH RISK** | Proceed with Caution |
| **0 - 39** | **VERY HIGH RISK** | Not Recommended |

---

## Recommended Broker Actions
Based on the generated insights, brokers are encouraged to perform the following follow-ups:
1. **📋 Income Verification**: Request recent pay stubs or bank statements.
2. **📞 Employment Check**: Contact supervisors for listed jobs.
3. **🏠 Reference Check**: Reach out to previous landlords.
4. **💳 Financial Check**: Run a formal credit report to verify the scores generated by the ruleset.
