# Project State Summary & Architectural Documentation

**Last Updated:** November 2025
**Status:** Active Development / Stabilization Phase

This document serves as the single source of truth for the DoorWay project's architectural state, core logic, and known technical debt following the recent audit and stabilization missions.

---

## 1. System Structure & User Roles

The system is built on a Django backend with a clear separation of concerns across four primary applications.

### Core User Roles
Permissions are defined in `users/models.py` using boolean flags on the custom `User` model.

| Role | System Flag | Permissions & Constraints |
|------|-------------|---------------------------|
| **Applicant** | `is_applicant=True` | **Primary User.** Can complete their profile, view matched apartments, and submit applications. Restricted to their own data. |
| **Broker** | `is_broker=True` | **Manager.** Can create new applications, invite applicants, and view full profiles of applicants assigned to them. **Constraint:** Must be explicitly assigned to an Applicant/Application to view data. |
| **Admin Superuser** | `is_superuser=True` | **System Admin.** Full access to all data, settings, and configurations. Can manage all users and buildings. |
| **Owner** | `is_owner=True` | **Building Manager.** (Limited Scope) Can view building-specific data. Not an admin. |

### Application Architecture
The codebase is split into four main Django apps, each with a specific domain responsibility:

*   **/users**: Handles Authentication and the core `User` model.
    *   *Key Models:* `User` (Custom Auth).
*   **/applicants**: Manages the detailed Applicant Profile and Intelligence logic.
    *   *Key Models:* `Applicant` (Profile Data), `SmartInsights` (Logic), `ApartmentMatchingService` (Logic).
    *   *Fragmentation Point:* The `Applicant` profile is a separate model linked One-to-One with `User`, rather than being part of the `User` model itself.
*   **/applications**: Manages the Application Workflow and Nudge Service.
    *   *Key Models:* `Application` (The core transaction object), `NudgeService` (Logic).
*   **/apartments**: Manages Real Estate Inventory.
    *   *Key Models:* `Apartment`, `Building`.

---

## 2. Algorithm Clarity & Logic

The system employs two distinct algorithms to process applicant data, each serving a unique business purpose.

### A. Smart Insights (Qualifier / Risk Assessor)
*   **File:** `applicants/smart_insights.py`
*   **Business Purpose:** **Qualification & Risk Assessment.**
*   **Function:** Analyzes an applicant's financial and residential history to determine if they are a viable candidate. It produces a "Risk Score" and "Recommendations".
*   **Key Logic:**
    *   **Affordability:** Checks if Income >= 3x Rent (or 40x rule).
    *   **Stability:** Analyzes employment duration and residential history.
    *   **Privacy:** Purely rule-based (Python); NO external AI calls or PII sharing.

### B. Apartment Matching (Ranker / Recommender)
*   **File:** `applicants/apartment_matching.py`
*   **Business Purpose:** **Preference Matching & Ranking.**
*   **Function:** Ranks available apartments based on how well they fit the applicant's specific desires.
*   **Scoring Weights:**
    *   **60% - Basic Requirements:** Bedrooms, Bathrooms, Price, Neighborhood.
    *   **25% - Building Amenities:** "Must Have" vs "Nice to Have" building features.
    *   **15% - Apartment Amenities:** Unit-specific features.

---

## 3. Nudge Intelligence Data

The **Nudge Service** (`applications/nudge_service.py`) uses specific missing data points to prompt applicants. The following fields are identified as the most critical for the matching algorithm and are the primary triggers for nudges.

```json
{
    "critical_fields": [
        "annual_income",
        "max_rent_budget",
        "employment_start_date",
        "employment_status",
        "current_address_years"
    ],
    "description": "Top 5 most heavily weighted fields for the Smart Match Algorithm."
}
```

---

## 4. Architectural Debt & Decisions

### Critical Fixes Committed
1.  **Data Flow Stabilization:** Fixed integrity issues between `Application`, `Applicant`, and `Apartment` models.
2.  **Nudge Service Structure:** Implemented `NudgeService` in `/applications` to handle email reminders for missing critical data.
3.  **Algorithm Optimization:** `ApartmentMatchingService` now caches applicant preferences to prevent N+1 query performance issues.

### Pending Technical Debt (The "Fix List")
These items represent known architectural flaws to be addressed in future refactoring missions:

1.  **Model Fragmentation:**
    *   *Issue:* `Applicant` data is split between `users.User` (auth) and `applicants.Applicant` (profile).
    *   *Impact:* Requires complex joins and double-queries.
2.  **Data Redundancy:**
    *   *Issue:* Legacy field `length_at_current_address` (string) co-exists with structured `current_address_years` (int).
    *   *Impact:* Potential for data inconsistency if both aren't updated.
3.  **Cross-App Dependencies:**
    *   *Issue:* `Applicant` model has direct foreign keys to `apartments.Apartment` (for placement), creating tight coupling between apps.
    *   *Impact:* Makes it difficult to extract or refactor apps independently.
