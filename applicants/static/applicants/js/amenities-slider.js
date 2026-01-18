/**
 * Amenities Priority Slider System
 * 3-Level Priority: Nice to Have (2), Very Important (3), Must Have (4)
 * No selection = Don't Care (0)
 */

(function() {
    'use strict';
    
    // Wait for DOM to be ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAmenitiesSliders);
    } else {
        initAmenitiesSliders();
    }
    
    function initAmenitiesSliders() {
        // Prevent double initialization
        if (window.amenitiesSlidersInitialized) {
            console.log('Amenities sliders already initialized');
            return;
        }
        window.amenitiesSlidersInitialized = true;
        
        console.log('Initializing amenities priority sliders');
        
        // Find all amenity sliders
        const sliders = document.querySelectorAll('.amenity-slider');
        console.log('Found', sliders.length, 'amenity sliders');
        
        if (sliders.length === 0) {
            console.log('No amenity sliders found - amenities may not be rendered yet');
            return;
        }
        
        // Initialize each slider
        sliders.forEach(function(slider) {
            setupSlider(slider);
            loadExistingValue(slider);
        });
        
        console.log('Amenities sliders initialization complete');
    }
    
    /**
     * Set up individual slider with event handlers
     */
    function setupSlider(slider) {
        // Add input event listener
        slider.addEventListener('input', function() {
            updateSliderAppearance(this);
        });
        
        // Add change event for final value
        slider.addEventListener('change', function() {
            updateSliderAppearance(this);
        });
        
        // Set initial appearance
        updateSliderAppearance(slider);
    }
    
    /**
     * Update slider visual appearance based on value
     */
    function updateSliderAppearance(slider) {
        const value = parseInt(slider.value);
        const item = slider.closest('.amenity-slider-item');
        if (!item) return; // Guard clause for new layout if still present
        
        const label = item.querySelector('.priority-label');
        const amenityName = slider.dataset.amenityName || 'Unknown';
        
        // Reset all classes
        item.classList.remove('nice-to-have', 'very-important', 'must-have', 'unset');
        
        // Update based on value
        if (value === 0) {
            // Unset/Don't Care
            if (label) label.textContent = '';
            slider.className = 'amenity-slider unset';
            item.classList.add('unset');
            console.log(amenityName + ': Unset (Don\'t Care)');
            
        } else if (value === 1) {
            // Nice to Have
            if (label) label.textContent = 'Nice to Have';
            slider.className = 'amenity-slider nice-to-have';
            item.classList.add('nice-to-have');
            console.log(amenityName + ': Nice to Have');
            
        } else if (value === 2) {
            // Important (formerly Very Important)
            if (label) label.textContent = 'Important';
            slider.className = 'amenity-slider very-important';
            item.classList.add('very-important');
            console.log(amenityName + ': Important');
            
        } else if (value === 3) {
            // Must Have
            if (label) label.textContent = 'Must Have';
            slider.className = 'amenity-slider must-have';
            item.classList.add('must-have');
            console.log(amenityName + ': Must Have');
            
        } else {
            // Invalid value - reset to 0
            slider.value = 0;
            updateSliderAppearance(slider);
            return;
        }
    }
    
    /**
     * Load existing value from data attributes or hidden inputs
     */
    function loadExistingValue(slider) {
        // Check if there's an existing value in the slider's data
        const existingValue = slider.dataset.existingValue;
        
        if (existingValue && existingValue !== '0') {
            slider.value = existingValue;
            console.log('Loaded existing value:', existingValue, 'for', slider.dataset.amenityName);
        } else {
            slider.value = 0; // Default to unset
        }
        
        // Update appearance based on loaded value
        updateSliderAppearance(slider);
    }
    
    /**
     * Get all current slider values (for debugging or form submission)
     */
    function getAllSliderValues() {
        const values = {};
        document.querySelectorAll('.amenity-slider').forEach(function(slider) {
            const amenityId = slider.dataset.amenityId;
            const amenityType = slider.dataset.amenityType;
            const value = parseInt(slider.value);
            
            if (value > 0) { // Only include set values
                const key = amenityType + '_amenity_' + amenityId;
                values[key] = value;
            }
        });
        return values;
    }
    
    /**
     * Reset all sliders to unset (for testing)
     */
    function resetAllSliders() {
        document.querySelectorAll('.amenity-slider').forEach(function(slider) {
            slider.value = 0;
            updateSliderAppearance(slider);
        });
        console.log('All sliders reset to unset');
    }
    
    // Expose functions to global scope for debugging
    window.amenitiesSliderDebug = {
        getAllValues: getAllSliderValues,
        resetAll: resetAllSliders
    };
    
})();