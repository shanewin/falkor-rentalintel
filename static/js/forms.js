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
});

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
