# Smart Match Profile Requirements Analysis

## 1. Strict Gating Requirements (Mandatory)
To enable "Strict Mode," the following fields **MUST** be populated. If *any* are missing, the algorithm **returns 0 matches** immediately.

### Neighborhood Preferences (Critical)
*   **Field**: `applicant.neighborhood_preferences` (Related Manager)
*   **Ranking Logic**: Prioritizes user's ordered choices.
    *   **1st Choice**: **100% Score**
    *   **2nd Choice**: **90% Score**
    *   **3rd Choice**: **80% Score**
    *   **4th Choice**: **70% Score**
    *   **Non-Selected Neighborhood**: **40% Score** (Allows for "Good Matches" if apartment is otherwise perfect).
*   **Requirement**: User **MUST** select at least one neighborhood.

### Maximum Rent Budget (Critical)
*   **Field**: `applicant.max_rent_budget`
*   **Current Usage**:
    *   **Filter**: Filters out apartments > 10% over budget.
    *   **Score**: Accounts for distinct penalties (3%, 6%, 10% buckets).
*   **Requirement**: User **MUST** set a valid numeric budget (> $0).

### Bedroom Preferences (High Priority)
*   **Fields**: `applicant.min_bedrooms` AND `applicant.max_bedrooms`
*   **Current Usage**:
    *   **Filter**: Removes apartments outside the range (with logic for studios vs 1-bed).
    *   **Score**: Penalizes mismatches.
*   **Requirement**: User **MUST** specify a minimum bedroom preference.

---

## 2. Pet Policy Logic (Strict Filter + Weighted Score)
**Field**: `applicant.pets`
**Status**: **Mixed**.
*   **Empty List**: Treated as "No Pets". This is a **valid state**. Matches ALL buildings (Score: 100% for this factor).
*   **Populated List**: Triggers **Strict Filters** AND **Scoring Adjustments**.

### Strict Filters (Dealbreakers)
These conditions effectively remove the apartment from the result set ("User cannot and will not live there"):
1.  **Strict Ban**: If user has **ANY** pets and building is `no_pets` -> **EXCLUDED**.
2.  **Species Mismatch**: If user has **Non-Cat** (e.g., Dog) and building is `cats_only` -> **EXCLUDED**.

### Scoring Implementation (Weighted Logic)
For apartments that pass the strict filter, the following weights are applied (part of 60% Basic Requirements match):
*   **"All Pets Allowed"**: **100% Score** (Perfect Match).
*   **"Pet Fee"**: **95% Score** (Minor Penalty).
    *   *Logic*: "Minor penalty for people with pets... almost a sure thing."
*   **"Case by Case"**: **80% Score** (Strong Consideration).
    *   *Logic*: "Definite consideration, but not a slam dunk."
*   **"Small Pets"**: Logic checks weight limits (if available) or applies moderate penalty.
*   **"Cats Only"** (for Cat owners): **95% Score**.

---

## 3. Scoring Factors (Conditional & Weighted)
These fields affect the score but do not strictly filter results if left empty.

### Bathroom Preferences
*   **Fields**: `applicant.min_bathrooms`
*   **Impact**: Penalizes score if the apartment has fewer bathrooms than requested.
*   **Default**: If missing, assumes 1 Bathroom minimum.

---

## 4. Amenity Optimization (Bonus/Penalty)
**Weight**: 40% Total (25% Building + 15% Apartment)

*   **Fields**: `building_amenity_preferences`, `apartment_amenity_preferences`
*   **Logic**:
    *   **Must Have**: Huge Penalty if missing (-50 points).
    *   **Important**: Moderate Penalty if missing (-15 points).
    *   **Nice to Have**: Bonus if present, no penalty if missing.
*   **Strictness**: If a user selects *no* amenities, they receive a neutral 100% score for this section.

---

## 5. Required Data Fields for Apartment Matching Algorithm
The following is a list of ALL form fields that impact the "Smart Match" algorithm (determining which apartments comprise the user's recommended list).

*   **`neighborhood_preferences`** (Many-to-Many): The user's ranked list of desired locations.
*   **`max_rent_budget`**: The absolute hard line for affordability matching.
*   **`min_bedrooms` / `max_bedrooms`**: The size constraint.
*   **`min_bathrooms`**: A secondary comfort constraint.
*   **`pets`** (Related Manager):
    *   `pet_type` (e.g., Dog, Cat) - **Critical for filtering**.
    *   `weight` (for "Small Pets" policies).
    *   `breed` (potentially for insurance restrictions).
*   **`building_amenity_preferences`**: (e.g., Doorman, Gym, Elevator, Laundry).
*   **`apartment_amenity_preferences`**: (e.g., Dishwasher, Balcony, In-Unit Laundry).
*   **`desired_move_in_date`**: Used to match against apartment availability date.
