/* Smart Insights UI Enhancements
 * Highlights fields that feed into the Smart Insights algorithm
 * and adds tooltips to explain their importance.
 * 
 * Logic:
 * - Highlights are applied ONLY if the field is empty (not filled out/saved).
 * - Tooltips are applied ONLY if the field is empty.
 */

document.addEventListener('DOMContentLoaded', function() {
    'use strict';

    // Configuration for Smart Insights fields
    const smartInsightsConfig = {
        // Step 1: Personal Info
        '#div_id_email': 'This is required for profile completeness (Red Flag check).',
        '#div_id_phone_number': 'This is required for profile completeness (Red Flag check).',
        '#div_id_current_address_years': 'Measures geographic stability (Rental History).',
        '#div_id_current_address_months': 'Measures geographic stability (Rental History).',
        '#div_id_housing_status': 'Determines if you are a current renter or homeowner (Rental History).',
        '#is_rental_checkbox': 'Determines if you are a current renter or homeowner (Rental History).',
        '#div_id_current_landlord_name': 'Providing a reference adds verification points.',
        '#div_id_evicted_before': 'Eviction history is a critical risk factor.',
        '#div_id_emergency_contact_name': 'Influences analysis confidence level.',
        '#add-previous-address-btn': 'Adding previous addresses reduces risk by showing stability.',

        // Step 2: Housing Needs
        '#div_id_max_rent_budget': 'Used to calculate your affordability ratio (Income vs. Rent).',

        // Step 3: Employment & Income
        '#div_id_annual_income': 'Primary factor for Affordability Score (Income support).',
        '#div_id_employment_status': 'Determines your employment stability score.',
        '#div_id_employment_start_date': 'Used to calculate employment tenure (Stability).',
        '#div_id_company_name': 'Identifies your primary income source.',
        '#add-job-btn': 'Secondary jobs add bonus points to your profile.',
        '#add-income-btn': 'Additional income sources improve your affordability ratio.'
    };

    /**
     * Checks if a field element or its container has a "filled" value.
     * @param {HTMLElement} element - The targeted container or input.
     * @returns {boolean} - True if the field has a value.
     */
    function isFieldFilled(element) {
        // 1. If 'element' is the input itself
        if (element.tagName === 'INPUT' || element.tagName === 'SELECT' || element.tagName === 'TEXTAREA') {
            return checkInputValue(element);
        }

        // 2. If 'element' is a container (e.g., div_id_...), find the input inside
        const input = element.querySelector('input, select, textarea');
        if (input) {
            return checkInputValue(input);
        }
        
        // 3. Special case: Buttons are "actions", not fields. 
        // We generally always highlight them unless we check for related data (complex).
        // For now, assume buttons are always "prompting" action unless we decide otherwise.
        if (element.tagName === 'BUTTON') {
            return false; // Always highlight buttons (prompts)
        }

        return false;
    }

    function checkInputValue(input) {
        if (input.type === 'checkbox' || input.type === 'radio') {
            return input.checked;
        }
        if (input.tagName === 'SELECT') {
            // Check if selected value is not empty string
            // Sometimes "Select an option..." has value=""
            return input.value && input.value.trim() !== '';
        }
        // Text, number, email, etc.
        return input.value && input.value.trim() !== '';
    }

    // Apply highlights and tooltips
    for (const [selector, message] of Object.entries(smartInsightsConfig)) {
        const elements = document.querySelectorAll(selector);
        
        elements.forEach(element => {
            // Check if field is already filled
            if (isFieldFilled(element)) {
                return; // Skip highlighting
            }

            // Add highlight class to wrapper if it's an input/select/textarea
            let targetForHighlight = element;
            if (element.tagName === 'INPUT' || element.tagName === 'SELECT' || element.tagName === 'TEXTAREA') {
                targetForHighlight = element.closest('.form-check') || element.closest('.mb-3') || element.parentElement;
            }
            targetForHighlight.classList.add('smart-insight-field');
            
            // Add tooltip
            if (!element.getAttribute('data-bs-toggle')) {
                if (element.tagName === 'BUTTON' || element.tagName === 'INPUT') {
                    element.setAttribute('data-bs-toggle', 'tooltip');
                    element.setAttribute('data-bs-placement', 'top'); 
                    element.setAttribute('title', message);
                    new bootstrap.Tooltip(element);
                } else {
                    // Wrapper div
                    const label = element.querySelector('label');
                    if (label) {
                        const icon = document.createElement('i');
                        icon.className = 'fas fa-lightbulb text-info ms-2 smart-insight-icon';
                        icon.setAttribute('data-bs-toggle', 'tooltip');
                        icon.setAttribute('data-bs-placement', 'right');
                        icon.setAttribute('title', message);
                        label.appendChild(icon);
                        new bootstrap.Tooltip(icon);
                    }
                }
            }
        });
    }

    // Dynamic field handling
    const observerConfig = { childList: true, subtree: true };
    const dynamicContainers = [
        '#jobs-list', '#jobs-list-employed', 
        '#income-list', '#income-list-employed',
        '#previous-addresses-container'
    ];

    dynamicContainers.forEach(containerId => {
        const container = document.querySelector(containerId);
        if (container) {
            const observer = new MutationObserver(function(mutations) {
                mutations.forEach(function(mutation) {
                    if (mutation.addedNodes.length) {
                        applyDynamicHighlights(mutation.addedNodes);
                    }
                });
            });
            observer.observe(container, observerConfig);
        }
    });

    function applyDynamicHighlights(nodes) {
        nodes.forEach(node => {
            if (node.nodeType === 1) { // Element node
                const relevantInputs = node.querySelectorAll('input[name*="income"], input[name*="salary"], input[name*="rent"]');
                relevantInputs.forEach(input => {
                    // Check if filled (unlikely for new dynamic fields, but good practice)
                    if (isFieldFilled(input)) return;

                    const wrapper = input.closest('.mb-3') || input.parentElement;
                    wrapper.classList.add('smart-insight-field');
                    
                    const label = wrapper.querySelector('label');
                    if (label && !label.querySelector('.smart-insight-icon')) {
                        const icon = document.createElement('i');
                        icon.className = 'fas fa-lightbulb text-info ms-2 smart-insight-icon';
                        icon.setAttribute('data-bs-toggle', 'tooltip');
                        icon.setAttribute('data-bs-placement', 'right');
                        icon.setAttribute('title', 'This contributes to your financial stability score.');
                        label.appendChild(icon);
                        new bootstrap.Tooltip(icon);
                    }
                });
            }
        });
    }
});
