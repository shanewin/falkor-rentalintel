/**
 * Form handling utilities for Falkor application
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

/* ============================================================
   FALKOR AUTO-SAVE ENGINE
   AJAX-first field-level autosave for Profile & Application forms.

   Usage:  add  data-autosave-url="/path/to/autosave/"  to any <form>.
           For token-protected application forms, also add
           data-autosave-token="{{ token }}"  on the form.

   Excluded from autosave:
     - input[type=file]        (uploads require explicit submit)
     - input[name=csrfmiddlewaretoken]
     - Fields inside .no-autosave containers (pet rows, address rows, jobs)

   NOTE (future work): M2M fields (amenity sliders, neighborhood rankings,
   pet records, address rows, job records) are intentionally excluded from
   autosave because they require complex nested serialization. These should
   be wired in a later pass using dedicated AJAX sub-endpoints.
   ============================================================ */

(function () {
    'use strict';

    // ── Configuration ─────────────────────────────────────────
    const DEBOUNCE_MS   = 1500;   // wait this long after user stops typing
    const BADGE_TTL_OK  = 2500;   // how long "✓ Saved" stays visible (ms)
    const LS_PREFIX     = 'falkor-autosave:';

    // ── Singleton badge ────────────────────────────────────────
    let _badge = null;
    let _badgeTimeout = null;

    function getBadge() {
        if (!_badge) {
            _badge = document.createElement('div');
            _badge.id = 'falkor-autosave-badge';
            _badge.style.cssText = [
                'position:fixed', 'bottom:24px', 'right:24px',
                'padding:8px 16px', 'border-radius:8px',
                'font-size:13px', 'font-weight:500',
                'display:flex', 'align-items:center', 'gap:6px',
                'box-shadow:0 2px 8px rgba(0,0,0,.18)',
                'z-index:9999', 'transition:opacity .3s ease',
                'opacity:0', 'pointer-events:none',
            ].join(';');
            document.body.appendChild(_badge);
        }
        return _badge;
    }

    function showBadge(state) {
        const badge = getBadge();
        clearTimeout(_badgeTimeout);

        const styles = {
            saving: { bg: '#6c757d', text: 'white', icon: '⏳', label: 'Saving\u2026' },
            saved:  { bg: '#198754', text: 'white', icon: '✓',  label: 'Saved'         },
            error:  { bg: '#dc3545', text: 'white', icon: '⚠',  label: 'Save failed'   },
        };
        const s = styles[state] || styles.saving;

        badge.style.background  = s.bg;
        badge.style.color       = s.text;
        badge.innerHTML         = '<span>' + s.icon + '</span><span>' + s.label + '</span>';
        badge.style.opacity     = '1';

        if (state === 'saved') {
            _badgeTimeout = setTimeout(function() { badge.style.opacity = '0'; }, BADGE_TTL_OK);
        }
        // 'error' persists until next save attempt
    }

    // ── CSRF helper ─────────────────────────────────────────────
    function getCsrf() {
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
    }

    // ── Collect saveable fields ─────────────────────────────────
    var SKIP_TYPES  = {'file':1,'submit':1,'button':1,'image':1,'reset':1,'hidden':1};
    var SKIP_NAMES  = {'csrfmiddlewaretoken':1};

    function collectFields(form) {
        var data   = {};
        var inputs = form.querySelectorAll('input, select, textarea');

        inputs.forEach(function(el) {
            if (!el.name) return;
            if (SKIP_NAMES[el.name]) return;
            if (el.type && SKIP_TYPES[el.type]) return;
            if (el.closest('.no-autosave')) return;

            if (el.type === 'checkbox') {
                data[el.name] = el.checked ? 'true' : 'false';
            } else if (el.type === 'radio') {
                if (el.checked) data[el.name] = el.value;
            } else {
                data[el.name] = el.value;
            }
        });

        return data;
    }

    // ── Send to server ──────────────────────────────────────────
    function postAutosave(url, token, data) {
        var body = new URLSearchParams(data);
        body.append('csrfmiddlewaretoken', getCsrf());
        if (token) body.append('autosave_token', token);

        return fetch(url, {
            method:  'POST',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            body:    body,
        }).then(function(resp) {
            if (!resp.ok) throw new Error('HTTP ' + resp.status);
            return resp.json();
        }).then(function(json) {
            if (json.status !== 'ok') throw new Error(json.message || 'Server error');
        });
    }

    // ── Per-form watcher ────────────────────────────────────────
    function initFormAutosave(form) {
        var url   = form.dataset.autosaveUrl;
        var token = form.dataset.autosaveToken || '';
        var lsKey = LS_PREFIX + (form.id || url);

        if (!url) return;

        var timer = null;

        function triggerSave() {
            var data = collectFields(form);
            showBadge('saving');

            postAutosave(url, token, data).then(function() {
                try { localStorage.setItem(lsKey, JSON.stringify(data)); } catch(e) {}
                showBadge('saved');
            }).catch(function(err) {
                console.warn('[autosave] Server save failed, using localStorage fallback:', err);
                try { localStorage.setItem(lsKey, JSON.stringify(data)); } catch(e) {}
                showBadge('error');
            });
        }

        function onActivity(e) {
            if (e.target.type === 'file') return;
            if (e.target.closest && e.target.closest('.no-autosave')) return;
            clearTimeout(timer);
            timer = setTimeout(triggerSave, DEBOUNCE_MS);
        }

        form.addEventListener('input',  onActivity);
        form.addEventListener('change', onActivity);

        // On submit, cancel pending save and clear localStorage draft
        form.addEventListener('submit', function() {
            clearTimeout(timer);
            try { localStorage.removeItem(lsKey); } catch(e) {}
        });
    }

    // ── Boot ────────────────────────────────────────────────────
    document.addEventListener('DOMContentLoaded', function() {
        document.querySelectorAll('form[data-autosave-url]').forEach(initFormAutosave);
    });

}());
