/* ================================================
   DOORWAY FORMS - Unified Form Behavior
   Consistent form interactions across all pages
   ================================================ */

document.addEventListener('DOMContentLoaded', function() {
    
    // ================================================
    // Initialize all Doorway forms
    // ================================================
    function initializeDoorwayForms() {
        // Find all forms with doorway-form class
        const forms = document.querySelectorAll('.doorway-form');
        
        forms.forEach(form => {
            initializeFormFields(form);
            initializeFormValidation(form);
        });
    }
    
    // ================================================
    // Field Highlighting - Empty Required Fields
    // ================================================
    function initializeFormFields(form) {
        const formFields = form.querySelectorAll('input.form-control, textarea.form-control, select.form-control, select.form-select');
        
        formFields.forEach(field => {
            // Function to check and update field state
            function updateFieldState() {
                // Remove all state classes first
                field.classList.remove('is-empty-required', 'has-data');
                
                const value = field.value ? field.value.trim() : '';
                
                if (value === '') {
                    // Check if field is required or important
                    if (field.hasAttribute('required') || isImportantField(field)) {
                        field.classList.add('is-empty-required');
                    }
                } else {
                    // Optional: Add has-data class for filled fields
                    // field.classList.add('has-data');
                }
            }
            
            // Check initial state
            updateFieldState();
            
            // Add event listeners for dynamic updates
            field.addEventListener('input', updateFieldState);
            field.addEventListener('change', updateFieldState);
            field.addEventListener('blur', updateFieldState);
        });
    }
    
    // ================================================
    // Determine if field is important (customize per form)
    // ================================================
    function isImportantField(field) {
        const importantFields = [
            'name', 'first_name', 'last_name', 'email',
            'address', 'state',
            'building_name', 'position', 'title'
        ];
        
        return importantFields.includes(field.name);
    }
    
    // ================================================
    // Form Validation Enhancement
    // ================================================
    function initializeFormValidation(form) {
        form.addEventListener('submit', function(e) {
            let isValid = true;
            const requiredFields = form.querySelectorAll('[required]');
            
            requiredFields.forEach(field => {
                if (!field.value || field.value.trim() === '') {
                    isValid = false;
                    field.classList.add('is-invalid');
                    
                    // Add error message if not exists
                    if (!field.nextElementSibling || !field.nextElementSibling.classList.contains('invalid-feedback')) {
                        const errorDiv = document.createElement('div');
                        errorDiv.className = 'invalid-feedback';
                        errorDiv.textContent = 'This field is required.';
                        field.parentNode.insertBefore(errorDiv, field.nextSibling);
                    }
                } else {
                    field.classList.remove('is-invalid');
                    // Remove error message if exists
                    if (field.nextElementSibling && field.nextElementSibling.classList.contains('invalid-feedback')) {
                        field.nextElementSibling.remove();
                    }
                }
            });
            
            if (!isValid) {
                e.preventDefault();
                // Scroll to first error
                const firstError = form.querySelector('.is-invalid');
                if (firstError) {
                    firstError.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstError.focus();
                }
            }
        });
    }
    
    // ================================================
    // Auto-save Draft (optional feature)
    // ================================================
    function initializeAutoSave(form) {
        if (!form.dataset.autosave) return;
        
        const formId = form.id || 'doorway-form';
        const saveKey = `doorway-draft-${formId}`;
        
        // Load saved draft on page load
        const savedData = localStorage.getItem(saveKey);
        if (savedData) {
            const data = JSON.parse(savedData);
            Object.keys(data).forEach(key => {
                const field = form.querySelector(`[name="${key}"]`);
                if (field) {
                    field.value = data[key];
                }
            });
        }
        
        // Save draft on input
        let saveTimeout;
        form.addEventListener('input', function() {
            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(() => {
                const formData = new FormData(form);
                const data = {};
                formData.forEach((value, key) => {
                    data[key] = value;
                });
                localStorage.setItem(saveKey, JSON.stringify(data));
                showAutoSaveIndicator();
            }, 1000);
        });
        
        // Clear draft on successful submit
        form.addEventListener('submit', function() {
            localStorage.removeItem(saveKey);
        });
    }
    
    // ================================================
    // Show auto-save indicator
    // ================================================
    function showAutoSaveIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'autosave-indicator';
        indicator.innerHTML = '<i class="fas fa-check"></i> Draft saved';
        indicator.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #28a745;
            color: white;
            padding: 10px 20px;
            border-radius: 4px;
            z-index: 1000;
            animation: fadeInOut 2s ease;
        `;
        
        document.body.appendChild(indicator);
        setTimeout(() => indicator.remove(), 2000);
    }
    
    // ================================================
    // Character Counter for Textareas
    // ================================================
    function initializeCharacterCounters() {
        const textareas = document.querySelectorAll('textarea[maxlength]');
        
        textareas.forEach(textarea => {
            const maxLength = textarea.getAttribute('maxlength');
            const counter = document.createElement('small');
            counter.className = 'character-counter text-muted';
            counter.style.display = 'block';
            counter.style.marginTop = '5px';
            
            function updateCounter() {
                const remaining = maxLength - textarea.value.length;
                counter.textContent = `${remaining} characters remaining`;
                
                if (remaining < 20) {
                    counter.classList.add('text-warning');
                } else {
                    counter.classList.remove('text-warning');
                }
            }
            
            updateCounter();
            textarea.addEventListener('input', updateCounter);
            textarea.parentNode.appendChild(counter);
        });
    }
    
    // ================================================
    // Buildings-Specific Functionality
    // ================================================
    function initializeBuildingsFunctions() {
        // Initialize Bootstrap popovers for help text
        initializePopovers();
        
        // Initialize currency formatting
        initializeCurrencyFields();
        
        // Initialize Select2 dropdowns
        initializeSelect2();
    }
    
    function initializePopovers() {
        // Use Bootstrap 5 syntax instead of jQuery
        const popoverTriggerList = document.querySelectorAll('[data-bs-toggle="popover"]');
        popoverTriggerList.forEach(function(popoverTriggerEl) {
            new bootstrap.Popover(popoverTriggerEl, {
                trigger: 'hover',
                placement: 'right',
                container: 'body',
                html: true
            });
        });
    }
    
    function initializeCurrencyFields() {
        const currencyFields = document.querySelectorAll('.currency-field');
        
        currencyFields.forEach(field => {
            // Add $ symbol overlay
            const wrapper = document.createElement('div');
            wrapper.style.position = 'relative';
            wrapper.style.display = 'inline-block';
            wrapper.style.width = '100%';
            
            const dollarSign = document.createElement('span');
            dollarSign.textContent = '$';
            dollarSign.style.position = 'absolute';
            dollarSign.style.left = '12px';
            dollarSign.style.top = '50%';
            dollarSign.style.transform = 'translateY(-50%)';
            dollarSign.style.color = '#6c757d';
            dollarSign.style.fontWeight = '500';
            dollarSign.style.fontSize = '16px';
            dollarSign.style.pointerEvents = 'none';
            dollarSign.style.zIndex = '10';
            
            field.parentNode.insertBefore(wrapper, field);
            wrapper.appendChild(dollarSign);
            wrapper.appendChild(field);
            
            // Format initial value
            if (field.value) {
                field.value = formatCurrencyInput(field.value);
            }
            
            // Add event listeners
            field.addEventListener('blur', function() {
                this.value = formatCurrencyInput(this.value);
            });
            
            field.addEventListener('focus', function() {
                this.value = cleanCurrencyInput(this.value);
            });
            
            field.addEventListener('keydown', function(e) {
                if (!isValidCurrencyKey(e)) {
                    e.preventDefault();
                }
            });
        });
    }
    
    function initializeSelect2() {
        // Initialize Select2 only on select elements that explicitly have the select2 class
        if (typeof $ !== 'undefined' && $.fn.select2) {
            $('.doorway-form select.select2').select2({
                theme: 'bootstrap-5',
                width: '100%',
                placeholder: function() {
                    return $(this).data('placeholder') || 'Select an option';
                },
                allowClear: false
            });
        }
        
        // Initialize commission pay type conditional logic
        initializeCommissionLogic();
    }
    
    function initializeCommissionLogic() {
        const commissionPayType = document.querySelector('select[name="commission_pay_type"]');
        const percentFields = document.querySelectorAll('.commission-percent-field');
        
        if (commissionPayType && percentFields.length > 0) {
            function togglePercentFields() {
                const shouldShow = commissionPayType.value === 'owner_and_tenant_pays';
                percentFields.forEach(field => {
                    field.style.display = shouldShow ? 'block' : 'none';
                });
                
                // Clear fields when hiding
                if (!shouldShow) {
                    const ownerField = document.querySelector('input[name="commission_owner_percent"]');
                    const tenantField = document.querySelector('input[name="commission_tenant_percent"]');
                    if (ownerField) ownerField.value = '';
                    if (tenantField) tenantField.value = '';
                }
            }
            
            // Initial state - hide by default
            percentFields.forEach(field => {
                field.style.display = 'none';
            });
            
            // Listen for regular change events
            commissionPayType.addEventListener('change', togglePercentFields);
            
            // Listen for Select2 change events specifically
            if (typeof $ !== 'undefined' && $.fn.select2) {
                $(commissionPayType).on('select2:select', function() {
                    setTimeout(togglePercentFields, 100); // Small delay to ensure value is updated
                });
            }
        }
        
        // Initialize auto-calculation for commission percentages
        initializePercentCalculation();
    }
    
    function initializePercentCalculation() {
        const ownerField = document.querySelector('input[name="commission_owner_percent"]');
        const tenantField = document.querySelector('input[name="commission_tenant_percent"]');
        
        if (ownerField && tenantField) {
            function calculateComplement(inputField, outputField) {
                const value = parseInt(inputField.value) || 0;
                if (value >= 0 && value <= 100) {
                    const complement = 100 - value;
                    outputField.value = complement;
                } else if (value > 100) {
                    inputField.value = 100;
                    outputField.value = 0;
                } else if (value < 0) {
                    inputField.value = 0;
                    outputField.value = 100;
                }
            }
            
            ownerField.addEventListener('input', function() {
                calculateComplement(this, tenantField);
            });
            
            tenantField.addEventListener('input', function() {
                calculateComplement(this, ownerField);
            });
        }
    }
    
    // Currency formatting helper functions
    function cleanCurrencyInput(value) {
        return value.replace(/[^0-9.]/g, '');
    }
    
    function formatCurrencyInput(value) {
        const cleaned = cleanCurrencyInput(value);
        if (!cleaned) return '';
        
        const num = parseFloat(cleaned);
        return isNaN(num) ? '' : num.toLocaleString('en-US', {
            minimumFractionDigits: cleaned.includes('.') ? 2 : 0,
            maximumFractionDigits: 2
        });
    }
    
    function isValidCurrencyKey(e) {
        const allowedKeys = [
            'Backspace', 'Delete', 'Tab', 'Enter', 
            'ArrowLeft', 'ArrowRight', 'Home', 'End'
        ];
        
        return (
            (e.key >= '0' && e.key <= '9') ||
            (e.key === '.' && !e.target.value.includes('.')) ||
            allowedKeys.includes(e.key) ||
            (e.ctrlKey || e.metaKey) && ['a', 'c', 'v', 'x'].includes(e.key.toLowerCase())
        );
    }
    
    // ================================================
    // Initialize everything
    // ================================================
    initializeDoorwayForms();
    initializeCharacterCounters();
    initializeBuildingsFunctions();
    initializeAutoUpload();
    
    // ================================================
    // Auto-upload functionality for image fields
    // ================================================
    function initializeAutoUpload() {
        const autoUploadFields = document.querySelectorAll('.auto-upload-field');
        
        autoUploadFields.forEach(field => {
            field.addEventListener('change', function() {
                if (this.files && this.files.length > 0) {
                    // Show loading state
                    const fieldset = this.closest('fieldset');
                    if (fieldset) {
                        const legend = fieldset.querySelector('legend');
                        if (legend) {
                            legend.innerHTML = 'Upload Building Images <i class="fas fa-spinner fa-spin text-primary"></i>';
                        }
                    }
                    
                    // Auto-submit the form
                    this.form.submit();
                }
            });
        });
    }
    
    // Initialize auto-save for forms with data-autosave attribute
    document.querySelectorAll('form[data-autosave]').forEach(form => {
        initializeAutoSave(form);
    });
});

// ================================================
// Add fadeInOut animation
// ================================================
if (!document.querySelector('#doorway-forms-animations')) {
    const style = document.createElement('style');
    style.id = 'doorway-forms-animations';
    style.textContent = `
        @keyframes fadeInOut {
            0% { opacity: 0; transform: translateY(10px); }
            20% { opacity: 1; transform: translateY(0); }
            80% { opacity: 1; transform: translateY(0); }
            100% { opacity: 0; transform: translateY(-10px); }
        }
    `;
    document.head.appendChild(style);
}

// ================================================
// Phone Number Formatting
// ================================================
function formatPhoneNumber(value) {
    // Remove all non-digit characters
    const phoneNumber = value.replace(/\D/g, '');
    
    // Format as (XXX) XXX-XXXX
    if (phoneNumber.length >= 6) {
        return `(${phoneNumber.slice(0, 3)}) ${phoneNumber.slice(3, 6)}-${phoneNumber.slice(6, 10)}`;
    } else if (phoneNumber.length >= 3) {
        return `(${phoneNumber.slice(0, 3)}) ${phoneNumber.slice(3)}`;
    } else if (phoneNumber.length > 0) {
        return `(${phoneNumber}`;
    }
    return '';
}

// Initialize phone formatting for all phone fields
document.addEventListener('DOMContentLoaded', function() {
    const phoneFields = document.querySelectorAll('input[name="phone_number"], input[name*="phone"]');
    
    phoneFields.forEach(field => {
        field.addEventListener('input', function(e) {
            const cursorPosition = e.target.selectionStart;
            const oldValue = e.target.value;
            const formatted = formatPhoneNumber(e.target.value);
            
            e.target.value = formatted;
            
            // Adjust cursor position to account for formatting
            let newCursorPosition = cursorPosition;
            if (formatted.length > oldValue.length) {
                newCursorPosition = Math.min(cursorPosition + 1, formatted.length);
            }
            e.target.setSelectionRange(newCursorPosition, newCursorPosition);
        });
        
        // Format on blur to ensure consistency
        field.addEventListener('blur', function(e) {
            e.target.value = formatPhoneNumber(e.target.value);
        });
    });
});