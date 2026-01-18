/**
 * Form handling utilities for DoorWay application
 */

document.addEventListener('DOMContentLoaded', function() {
    // Phone Number Formatting
    const phoneInputs = document.querySelectorAll('input[name*="phone"], input[id*="phone"]');
    
    phoneInputs.forEach(input => {
        // Format on initialization if value exists
        if (input.value) {
            input.value = formatPhoneNumber(input.value);
        }
        
        // Format as user types
        input.addEventListener('input', function(e) {
            const cursorPosition = this.selectionStart;
            const originalLength = this.value.length;
            
            const formatted = formatPhoneNumber(this.value);
            this.value = formatted;
            
            // Try to preserve cursor position (basic approximation)
            if (formatted.length > originalLength) {
                this.setSelectionRange(cursorPosition + 1, cursorPosition + 1);
            } else {
                this.setSelectionRange(cursorPosition, cursorPosition);
            }
        });
        
        // Ensure format on blur
        input.addEventListener('blur', function() {
            this.value = formatPhoneNumber(this.value);
        });
    });

    // Universal Currency Formatting
    document.querySelectorAll('.currency-input').forEach(input => {
        setupCurrencyInput(input);
    });
});

/**
 * Setup currency formatting for an input field
 * @param {HTMLInputElement} input - The input element to setup
 */
function setupCurrencyInput(input) {
    if (!input) return;

    const formatCurrency = (value) => {
        const numeric = value.replace(/[^0-9.]/g, '');
        if (!numeric) return '';
        const parts = numeric.split('.');
        const whole = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        const decimal = parts[1] !== undefined ? '.' + parts[1].slice(0, 2) : '';
        return whole + decimal;
    };

    const handleInput = (event) => {
        const start = input.selectionStart;
        const oldValue = input.value;
        const newValue = formatCurrency(oldValue);
        
        if (oldValue !== newValue) {
            input.value = newValue;
            // Basic cursor position preservation
            const diff = newValue.length - oldValue.length;
            input.setSelectionRange(start + diff, start + diff);
        }
    };

    input.addEventListener('input', handleInput);
    
    input.addEventListener('blur', () => { 
        if (input.value) {
            const parts = input.value.replace(/,/g, '').split('.');
            const whole = parts[0];
            const decimal = parts[1] || '00';
            input.value = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',') + '.' + decimal.slice(0, 2).padEnd(2, '0');
        }
    });

    const form = input.closest('form');
    if (form) {
        form.addEventListener('submit', () => {
            // Only strip commas if it's a standard form submission
            // For AJAX, let the AJAX handler decide
            input.value = input.value.replace(/,/g, '');
        });
    }

    // Initial format
    if (input.value) {
        input.value = formatCurrency(input.value);
        if (!input.value.includes('.')) {
            input.value += '.00';
        } else if (input.value.split('.')[1].length === 1) {
            input.value += '0';
        }
    }
}

/**
 * Format string as US phone number (XXX) XXX-XXXX
 * @param {string} value - The input string
 * @returns {string} - Formatted phone number
 */
function formatPhoneNumber(value) {
    if (!value) return value;
    
    // Strip all non-digits
    const phoneNumber = value.replace(/\D/g, '');
    
    // Setup formatting based on length
    if (phoneNumber.length < 4) {
        return phoneNumber;
    } else if (phoneNumber.length < 7) {
        return `(${phoneNumber.slice(0, 3)}) ${phoneNumber.slice(3)}`;
    } else {
        return `(${phoneNumber.slice(0, 3)}) ${phoneNumber.slice(3, 6)}-${phoneNumber.slice(6, 10)}`;
    }
}
