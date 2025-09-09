import re
from typing import Dict, List, Tuple
import hashlib
from datetime import datetime

class DocumentRedactor:
    """
    Redacts sensitive information from documents before sending to external APIs.
    Maintains a mapping to restore information if needed.
    """
    
    def __init__(self):
        self.redaction_map = {}
        self.session_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
    
    def redact_ssn(self, text: str) -> str:
        """Redact Social Security Numbers"""
        # Match SSN patterns: 123-45-6789, 123 45 6789, 123456789
        ssn_pattern = r'\b(\d{3}[-\s]?\d{2}[-\s]?\d{4})\b'
        
        def replace_ssn(match):
            ssn = match.group(0)
            token = f"[SSN-{self.session_id}-{len(self.redaction_map)}]"
            self.redaction_map[token] = ssn
            return token
        
        return re.sub(ssn_pattern, replace_ssn, text)
    
    def redact_account_numbers(self, text: str) -> str:
        """Redact bank account and credit card numbers"""
        # Bank account (8-17 digits)
        account_pattern = r'\b(\d{8,17})\b'
        
        # Credit card (13-19 digits, may have spaces/dashes)
        cc_pattern = r'\b(\d{4}[\s\-]?\d{4}[\s\-]?\d{4}[\s\-]?\d{1,7})\b'
        
        def replace_account(match):
            number = match.group(0)
            # Only redact if it looks like an account number (not a phone or date)
            if len(number.replace('-', '').replace(' ', '')) >= 8:
                token = f"[ACCT-{self.session_id}-{len(self.redaction_map)}]"
                self.redaction_map[token] = number
                return token
            return number
        
        text = re.sub(cc_pattern, replace_account, text)
        text = re.sub(account_pattern, replace_account, text)
        return text
    
    def redact_phone_numbers(self, text: str) -> str:
        """Redact phone numbers"""
        # US phone numbers: (123) 456-7890, 123-456-7890, etc.
        phone_pattern = r'\b(\(?\d{3}\)?[\s\-\.]?\d{3}[\s\-\.]?\d{4})\b'
        
        def replace_phone(match):
            phone = match.group(0)
            token = f"[PHONE-{self.session_id}-{len(self.redaction_map)}]"
            self.redaction_map[token] = phone
            return token
        
        return re.sub(phone_pattern, replace_phone, text)
    
    def redact_emails(self, text: str) -> str:
        """Redact email addresses"""
        email_pattern = r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
        
        def replace_email(match):
            email = match.group(0)
            # Keep domain for context
            username, domain = email.split('@')
            token = f"[EMAIL-{self.session_id}]@{domain}"
            self.redaction_map[token] = email
            return token
        
        return re.sub(email_pattern, replace_email, text)
    
    def redact_routing_numbers(self, text: str) -> str:
        """Redact bank routing numbers (9 digits)"""
        # ABA routing numbers are exactly 9 digits
        routing_pattern = r'\b(\d{9})\b'
        
        # Common routing number contexts
        context_keywords = ['routing', 'aba', 'rtn', 'transit']
        
        lines = text.split('\n')
        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in context_keywords):
                lines[i] = re.sub(routing_pattern, '[ROUTING-REDACTED]', line)
        
        return '\n'.join(lines)
    
    def redact_addresses(self, text: str) -> str:
        """Partially redact street addresses (keep city/state for context)"""
        # Match street addresses
        address_pattern = r'\b(\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Boulevard|Blvd|Way|Court|Ct)\.?)\b'
        
        def replace_address(match):
            token = f"[ADDRESS-{self.session_id}]"
            self.redaction_map[token] = match.group(0)
            return token
        
        return re.sub(address_pattern, replace_address, text, flags=re.IGNORECASE)
    
    def redact_ein_tin(self, text: str) -> str:
        """Redact Employer Identification Numbers (EIN/TIN)"""
        # EIN format: 12-3456789
        ein_pattern = r'\b(\d{2}[-\s]?\d{7})\b'
        
        return re.sub(ein_pattern, '[EIN-REDACTED]', text)
    
    def redact_names(self, text: str) -> str:
        """Redact personal names from bank statements"""
        lines = text.split('\n')
        redacted_lines = []
        
        # Look for common name patterns in bank statements
        name_indicators = [
            'account holder:', 'customer:', 'name:', 'account name:',
            'primary account holder:', 'account owner:', 'customer name:'
        ]
        
        for line in lines:
            line_lower = line.lower()
            modified_line = line
            
            # Check if line contains name indicators
            for indicator in name_indicators:
                if indicator in line_lower:
                    # Extract name after the indicator
                    parts = line.split(':')
                    if len(parts) >= 2:
                        name_part = parts[1].strip()
                        # Look for typical name patterns (First Last, First Middle Last)
                        name_match = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]*)*)\b', name_part)
                        if name_match:
                            name = name_match.group(1)
                            token = f"[NAME-{self.session_id}-{len(self.redaction_map)}]"
                            self.redaction_map[token] = name
                            modified_line = line.replace(name, token)
                    break
            
            # Also check for standalone name patterns at beginning of lines
            # (common in bank statement headers)
            if not any(indicator in line_lower for indicator in name_indicators):
                # Look for capitalized names at start of line or after common prefixes
                name_patterns = [
                    r'^([A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b',  # Start of line
                    r'(?:Dear|Mr\.|Mrs\.|Ms\.|Dr\.)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b',  # After titles
                ]
                
                for pattern in name_patterns:
                    match = re.search(pattern, line)
                    if match:
                        name = match.group(1)
                        # Only redact if it looks like a real name (not bank names, etc.)
                        if not any(word in name.lower() for word in ['bank', 'corp', 'inc', 'llc', 'company', 'credit', 'union']):
                            token = f"[NAME-{self.session_id}-{len(self.redaction_map)}]"
                            self.redaction_map[token] = name
                            modified_line = line.replace(name, token)
                        break
            
            redacted_lines.append(modified_line)
        
        return '\n'.join(redacted_lines)
    
    def redact_document(self, text: str, 
                       redact_options: Dict[str, bool] = None) -> Tuple[str, Dict]:
        """
        Main redaction function with configurable options.
        
        Args:
            text: Document text to redact
            redact_options: Dict of what to redact (default: all True)
        
        Returns:
            Tuple of (redacted_text, redaction_map)
        """
        if redact_options is None:
            redact_options = {
                'ssn': True,
                'account_numbers': True,
                'phone_numbers': True,
                'emails': True,
                'routing_numbers': True,
                'addresses': True,
                'ein_tin': True,
                'names': True
            }
        
        # Clear previous mappings
        self.redaction_map = {}
        
        # Apply redactions in order (names first to catch them before other redactions)
        if redact_options.get('names', True):
            text = self.redact_names(text)
        
        if redact_options.get('ssn', True):
            text = self.redact_ssn(text)
        
        if redact_options.get('account_numbers', True):
            text = self.redact_account_numbers(text)
        
        if redact_options.get('routing_numbers', True):
            text = self.redact_routing_numbers(text)
        
        if redact_options.get('phone_numbers', True):
            text = self.redact_phone_numbers(text)
        
        if redact_options.get('emails', True):
            text = self.redact_emails(text)
        
        if redact_options.get('addresses', True):
            text = self.redact_addresses(text)
        
        if redact_options.get('ein_tin', True):
            text = self.redact_ein_tin(text)
        
        return text, self.redaction_map
    
    def restore_redacted(self, text: str) -> str:
        """Restore redacted information using the mapping"""
        for token, original in self.redaction_map.items():
            text = text.replace(token, original)
        return text


# Example usage for bank statement analysis
def prepare_document_for_api(text: str) -> Tuple[str, Dict]:
    """
    Prepare document for external API by redacting sensitive info.
    
    Returns:
        Tuple of (redacted_text, redaction_map)
    """
    redactor = DocumentRedactor()
    
    # For bank statements, we might want to keep some info
    redact_options = {
        'names': True,          # Always redact personal names
        'ssn': True,            # Always redact
        'account_numbers': True, # Redact full account numbers
        'phone_numbers': False,  # Keep for context
        'emails': False,        # Keep for context
        'routing_numbers': True, # Always redact
        'addresses': True,      # Partial redaction
        'ein_tin': True        # Always redact
    }
    
    redacted_text, mapping = redactor.redact_document(text, redact_options)
    
    # Add redaction notice
    redacted_text = "[NOTICE: Sensitive information has been redacted]\n\n" + redacted_text
    
    return redacted_text, mapping


# Compliance checking
def check_for_remaining_sensitive_data(text: str) -> List[str]:
    """
    Final check for any remaining sensitive patterns.
    Returns list of potential issues found.
    """
    issues = []
    
    # Check for potential SSNs
    if re.search(r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b', text):
        issues.append("Possible SSN found")
    
    # Check for long digit sequences
    if re.search(r'\b\d{10,}\b', text):
        issues.append("Long digit sequence found (possible account number)")
    
    # Check for routing numbers
    if re.search(r'\b\d{9}\b', text) and 'routing' in text.lower():
        issues.append("Possible routing number found")
    
    return issues


if __name__ == "__main__":
    # Example usage
    sample_text = """
    Bank of America Statement
    Account Holder: John Doe
    SSN: 123-45-6789
    Account Number: 1234567890123456
    Routing Number: 123456789
    
    Address: 123 Main Street, San Francisco, CA 94105
    Phone: (415) 555-0123
    Email: john.doe@email.com
    
    Transactions:
    - Direct Deposit from Employer (EIN: 12-3456789): $5,000
    - Rent Payment: $2,500
    """
    
    redactor = DocumentRedactor()
    redacted, mapping = redactor.redact_document(sample_text)
    
    print("ORIGINAL:")
    print(sample_text)
    print("\nREDACTED:")
    print(redacted)
    print("\nMAPPING:")
    print(mapping)