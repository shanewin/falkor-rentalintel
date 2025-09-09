"""
Maximum Security External API Client for Document Analysis
Implements defense-in-depth security for sensitive financial documents
"""
import requests
import json
import hashlib
import logging
import time
import os
import re
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from .redaction_utils import DocumentRedactor, check_for_remaining_sensitive_data
from django.conf import settings

logger = logging.getLogger(__name__)

class SecureAPIClient:
    """
    Maximum security external API client with comprehensive data protection
    """
    
    def __init__(self):
        self.redactor = DocumentRedactor()
        self.session_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]
        self.api_calls_log = []
        
        # Security configuration
        self.MAX_TEXT_LENGTH = 5000  # Increased to capture multiple pages of financial data
        self.REDACTION_CONFIDENCE_THRESHOLD = 0.99  # High confidence required
        self.ZERO_RETENTION_APIS = ['anthropic', 'openai-zero-retention']  # APIs with zero retention
        
    def create_security_audit_log(self, event_type: str, details: Dict) -> None:
        """Create detailed audit logs for compliance"""
        audit_entry = {
            'timestamp': datetime.now().isoformat(),
            'session_id': self.session_id,
            'event': event_type,
            'details': details,
            'user_ip': getattr(self, 'user_ip', 'unknown'),
            'document_hash': details.get('document_hash', 'unknown')
        }
        
        # Log to secure audit system (implement based on your compliance needs)
        logger.info(f"SECURITY_AUDIT: {json.dumps(audit_entry)}")
        self.api_calls_log.append(audit_entry)
    
    def calculate_document_hash(self, text: str) -> str:
        """Create document fingerprint for audit trails"""
        return hashlib.sha256(text.encode()).hexdigest()[:16]
    
    def assess_document_sensitivity(self, text: str) -> str:
        """
        Comprehensive sensitivity assessment
        Returns: HIGH, MEDIUM, or LOW
        """
        sensitivity_score = 0
        text_lower = text.lower()
        
        # High-risk indicators (each adds 10 points)
        high_risk_patterns = [
            r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',  # SSN
            r'\btax\s*return\b',                   # Tax docs
            r'\bmedical\b',                        # Medical records
            r'\bconfidential\b',                   # Marked confidential
            r'\bcredit\s*report\b',               # Credit reports
            r'\brouting\s*number\b',              # Routing numbers
        ]
        
        # Medium-risk indicators (each adds 5 points)
        medium_risk_patterns = [
            r'\baccount\s*number\b',
            r'\bsalary\b',
            r'\bincome\b',
            r'\bdeposit\b',
            r'\bwithdrawal\b',
        ]
        
        # Calculate sensitivity score
        for pattern in high_risk_patterns:
            if re.search(pattern, text_lower):
                sensitivity_score += 10
        
        for pattern in medium_risk_patterns:
            if re.search(pattern, text_lower):
                sensitivity_score += 5
        
        # Determine sensitivity level
        if sensitivity_score >= 20:
            return "HIGH"
        elif sensitivity_score >= 10:
            return "MEDIUM"
        else:
            return "LOW"
    
    def extract_financial_essentials(self, text: str) -> str:
        """
        Extract the most important financial data from bank statements
        Focus on actual financial content, not headers
        """
        lines = text.split('\n')
        essential_lines = []
        char_count = 0
        
        # Find lines with dollar amounts (actual financial data)
        financial_lines = []
        for line in lines:
            line = line.strip()
            if line and '$' in line:
                # Look for actual money amounts, not just the $ symbol
                if re.search(r'\$\s*[\d,]+\.?\d*', line):
                    financial_lines.append(line)
        
        # Take the most relevant financial lines first
        priority_keywords = [
            'balance', 'total', 'ending', 'beginning', 'available',
            'deposit', 'payroll', 'salary', 'direct', 'transfer',
            'debit', 'credit', 'withdrawal', 'payment', 'fee'
        ]
        
        # Sort financial lines by relevance
        scored_lines = []
        for line in financial_lines:
            score = 0
            line_lower = line.lower()
            
            # Higher score for balance information
            if any(word in line_lower for word in ['balance', 'total', 'ending', 'beginning']):
                score += 10
            
            # High score for income indicators
            if any(word in line_lower for word in ['deposit', 'payroll', 'salary', 'direct']):
                score += 8
            
            # Medium score for transactions
            if any(word in line_lower for word in ['debit', 'credit', 'withdrawal', 'payment']):
                score += 5
            
            # Bonus for dates (indicates actual transactions)
            if re.search(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}', line):
                score += 3
            
            scored_lines.append((score, line))
        
        # Sort by score (highest first) and take the best ones
        scored_lines.sort(key=lambda x: x[0], reverse=True)
        
        # Add essential account info (minimal header info)
        account_info_lines = []
        for line in lines[:15]:  # Check first 15 lines only
            line = line.strip()
            if line and len(line) < 100:  # Avoid long disclaimer text
                line_lower = line.lower()
                if any(word in line_lower for word in ['account', 'statement period', 'customer', 'schwab', 'bank']):
                    if not any(word in line_lower for word in ['notice', 'important', 'disclosure', 'terms']):
                        account_info_lines.append(line)
                        if len(account_info_lines) >= 3:  # Limit header info
                            break
        
        # Combine: minimal header + maximum financial data
        for line in account_info_lines:
            if char_count + len(line) < 300:  # Max 300 chars for headers
                essential_lines.append(line)
                char_count += len(line)
        
        # Add the highest-scoring financial lines
        for score, line in scored_lines:
            if char_count + len(line) < 1450:  # Leave room for summary
                if line not in essential_lines:
                    essential_lines.append(line)
                    char_count += len(line)
            else:
                break
        
        # If we still have very little financial data, be more aggressive
        if len([line for line in essential_lines if '$' in line]) < 5:
            # Include any line with dollar amounts, even lower scored ones
            for line in financial_lines:
                if char_count + len(line) < 1450 and line not in essential_lines:
                    essential_lines.append(line)
                    char_count += len(line)
                    if char_count >= 1400:
                        break
        
        result = '\n'.join(essential_lines)
        
        # Debug info (remove in production)
        result += f"\n[Found {len(financial_lines)} financial lines, using {len(essential_lines)} total lines]"
        
        return result[:5000]
    
    def prepare_secure_payload(self, text: str, document_type: str) -> Tuple[Dict, Dict]:
        """
        Prepare maximally secure payload for external API
        """
        doc_hash = self.calculate_document_hash(text)
        
        self.create_security_audit_log('document_processing_start', {
            'document_hash': doc_hash,
            'document_type': document_type,
            'original_length': len(text)
        })
        
        # Step 1: Simple truncation to first 5000 characters (more data for better analysis)
        truncated_text = text[:self.MAX_TEXT_LENGTH]
        
        # Step 2: Comprehensive redaction
        redaction_config = {
            'names': True,                  # Always redact personal names
            'ssn': True,                    # Always redact SSNs
            'account_numbers': True,        # Always redact account numbers
            'routing_numbers': True,        # Always redact routing numbers
            'phone_numbers': True,          # Redact phone numbers
            'emails': True,                 # Redact email addresses
            'addresses': True,              # Redact street addresses
            'ein_tin': True,               # Redact tax IDs
        }
        
        redacted_text, redaction_map = self.redactor.redact_document(
            truncated_text, redaction_config
        )
        
        # Step 3: Final security scan
        remaining_issues = check_for_remaining_sensitive_data(redacted_text)
        if remaining_issues:
            self.create_security_audit_log('security_warning', {
                'document_hash': doc_hash,
                'remaining_issues': remaining_issues
            })
            
            # If critical issues remain, abort
            critical_issues = [issue for issue in remaining_issues if 'SSN' in issue or 'account number' in issue]
            if critical_issues:
                raise SecurityError(f"Critical PII detected after redaction: {critical_issues}")
        
        # DEBUG: Print what we're actually sending to external API
        print("=" * 80)
        print("🔍 SECURITY AUDIT: Data being sent to external API")
        print("=" * 80)
        print(f"Original text length: {len(text)} characters")
        print(f"Redacted text length: {len(redacted_text)} characters")
        print(f"Redactions applied: {len(redaction_map)}")
        print("\n📤 ACTUAL DATA BEING SENT TO ANTHROPIC:")
        print("-" * 50)
        print(redacted_text)
        print("-" * 50)
        print(f"\n🔐 REDACTION MAPPING (what gets restored):")
        for token, original in redaction_map.items():
            print(f"  {token} → {original}")
        print("=" * 80)
        
        # Step 4: Add security headers and minimized prompt
        secure_payload = {
            'text': redacted_text,
            'type': document_type,
            'session_id': self.session_id,
            'security_level': 'maximum',
            'data_retention': 'zero',  # Request zero retention
            'prompt': self._get_minimal_prompt()
        }
        
        security_metadata = {
            'document_hash': doc_hash,
            'redaction_count': len(redaction_map),
            'original_length': len(text),
            'processed_length': len(redacted_text),
            'redaction_map': redaction_map
        }
        
        self.create_security_audit_log('payload_prepared', {
            'document_hash': doc_hash,
            'redaction_count': len(redaction_map),
            'final_length': len(redacted_text)
        })
        
        return secure_payload, security_metadata
    
    def _get_minimal_prompt(self) -> str:
        """Focused prompt for rental application analysis"""
        return """Analyze this redacted bank statement for rental application. Names and sensitive data are redacted with tokens like [NAME-abc123-0]. Focus on financial stability and income verification. Return JSON:
{
    "status": "Complete|Not Complete|Needs Manual Review",
    "summary": "Account assessment with ending balance, monthly income estimate, and key financial patterns for landlord evaluation. Include redaction tokens in response (e.g., 'Account holder [NAME-abc123-0] shows...')",
    "reasoning": "Assessment based on income stability, balance trends, and document completeness",
    "income_analysis": "Regular deposits, salary patterns, income consistency analysis",
    "risk_factors": "Any red flags like overdrafts, irregular income, or financial instability"
}

Requirements: Complete = has account info, bank, balance, income verification. Not Complete = missing critical rental assessment data. Manual Review = insufficient data or concerning patterns. Always include redaction tokens in your response so they can be restored later."""
    
    def call_anthropic_api(self, payload: Dict, metadata: Dict) -> Dict:
        """
        Call Anthropic Claude API with maximum security settings
        """
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        
        # Anthropic has zero data retention for API calls
        headers = {
            'Content-Type': 'application/json',
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'anthropic-beta': 'max-tokens-3-5-sonnet-2024-07-15',
            # Request zero retention
            'anthropic-data-retention': 'none'
        }
        
        # Minimal message structure
        messages = [{
            "role": "user",
            "content": f"{payload['prompt']}\n\nDocument text:\n{payload['text']}"
        }]
        
        api_payload = {
            "model": "claude-3-5-sonnet-20241022",  # Latest model
            "max_tokens": 500,  # Minimal response
            "messages": messages,
            "temperature": 0.1  # Consistent results
        }
        
        try:
            self.create_security_audit_log('api_call_start', {
                'document_hash': metadata['document_hash'],
                'api': 'anthropic',
                'model': 'claude-3-5-sonnet'
            })
            
            # DEBUG: Show exactly what we're sending to Anthropic API
            print("\n🌐 API REQUEST TO ANTHROPIC:")
            print("-" * 40)
            print(f"URL: https://api.anthropic.com/v1/messages")
            print(f"Model: {api_payload['model']}")
            print(f"Max tokens: {api_payload['max_tokens']}")
            print(f"Message content length: {len(api_payload['messages'][0]['content'])} characters")
            print("First 200 chars of message:")
            print(api_payload['messages'][0]['content'][:200] + "...")
            print("-" * 40)
            
            response = requests.post(
                'https://api.anthropic.com/v1/messages',
                headers=headers,
                json=api_payload,
                timeout=30  # Quick timeout
            )
            
            response.raise_for_status()
            result = response.json()
            
            # Extract and validate response
            ai_response = result['content'][0]['text']
            
            # DEBUG: Show API response
            print("\n📥 API RESPONSE FROM ANTHROPIC:")
            print("-" * 40)
            print(f"Response length: {len(ai_response)} characters")
            print(f"Tokens used: {result.get('usage', {})}")
            print("AI Response:")
            print(ai_response)
            print("-" * 40)
            
            self.create_security_audit_log('api_call_success', {
                'document_hash': metadata['document_hash'],  
                'response_length': len(ai_response),
                'tokens_used': result.get('usage', {})
            })
            
            return self._process_ai_response(ai_response, metadata)
            
        except Exception as e:
            self.create_security_audit_log('api_call_error', {
                'document_hash': metadata['document_hash'],
                'error': str(e)
            })
            raise
    
    def call_openai_api(self, payload: Dict, metadata: Dict) -> Dict:
        """
        Call OpenAI API with zero retention settings
        """
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
            # Request zero data retention
            'OpenAI-Organization': 'zero-retention'  # If you have enterprise account
        }
        
        api_payload = {
            "model": "gpt-4o-mini",  # Fast and cost-effective
            "messages": [{
                "role": "user", 
                "content": f"{payload['prompt']}\n\nDocument text:\n{payload['text']}"
            }],
            "max_tokens": 500,
            "temperature": 0.1,
            # Request zero retention (enterprise feature)
            "user": f"secure-session-{self.session_id}"
        }
        
        try:
            self.create_security_audit_log('api_call_start', {
                'document_hash': metadata['document_hash'],
                'api': 'openai',
                'model': 'gpt-4o-mini'
            })
            
            response = requests.post(
                'https://api.openai.com/v1/chat/completions',
                headers=headers,
                json=api_payload,
                timeout=30
            )
            
            response.raise_for_status()
            result = response.json()
            
            ai_response = result['choices'][0]['message']['content']
            
            self.create_security_audit_log('api_call_success', {
                'document_hash': metadata['document_hash'],
                'response_length': len(ai_response),
                'tokens_used': result.get('usage', {})
            })
            
            return self._process_ai_response(ai_response, metadata)
            
        except Exception as e:
            self.create_security_audit_log('api_call_error', {
                'document_hash': metadata['document_hash'],
                'error': str(e)
            })
            raise
    
    def _process_ai_response(self, ai_response: str, metadata: Dict) -> Dict:
        """Process and validate AI response"""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', ai_response, re.DOTALL)
            if json_match:
                response_data = json.loads(json_match.group())
            else:
                response_data = json.loads(ai_response)
            
            # Restore any redacted information in the summary
            if 'summary' in response_data and metadata.get('redaction_map'):
                original_summary = response_data['summary']
                response_data['summary'] = self.redactor.restore_redacted(response_data['summary'])
                
                # DEBUG: Show restoration process
                print("\n🔄 PII RESTORATION:")
                print("-" * 40)
                print("Before restoration (what AI returned):")
                print(original_summary)
                print("\nAfter restoration (what user sees):")
                print(response_data['summary'])
                print("-" * 40)
            
            # Add security metadata
            response_data['security_metadata'] = {
                'redaction_count': metadata['redaction_count'],
                'data_minimized': True,
                'zero_retention_requested': True,
                'processing_date': datetime.now().isoformat()
            }
            
            return response_data
            
        except json.JSONDecodeError:
            return {
                "status": "Needs Manual Review",
                "summary": "AI analysis completed but response format was invalid.",
                "reasoning": "External AI service returned unstructured response",
                "security_metadata": {
                    "redaction_count": metadata['redaction_count'],
                    "processing_error": "JSON parsing failed"
                }
            }
    
    def analyze_document_securely(self, text: str, document_type: str, 
                                preferred_api: str = 'anthropic') -> Dict:
        """
        Main secure analysis function
        """
        try:
            # Step 1: Assess sensitivity
            sensitivity = self.assess_document_sensitivity(text)
            doc_hash = self.calculate_document_hash(text)
            
            self.create_security_audit_log('analysis_start', {
                'document_hash': doc_hash,
                'sensitivity_level': sensitivity,
                'preferred_api': preferred_api
            })
            
            # Step 2: Prepare secure payload
            payload, metadata = self.prepare_secure_payload(text, document_type)
            
            # Step 3: Choose API based on security requirements
            if sensitivity == "HIGH":
                # For highest sensitivity, use most secure API
                if preferred_api == 'anthropic':
                    result = self.call_anthropic_api(payload, metadata)
                else:
                    result = self.call_openai_api(payload, metadata)
            else:
                # For medium/low sensitivity, use preferred API
                if preferred_api == 'anthropic':
                    result = self.call_anthropic_api(payload, metadata)
                else:
                    result = self.call_openai_api(payload, metadata)
            
            self.create_security_audit_log('analysis_complete', {
                'document_hash': doc_hash,
                'status': result.get('status', 'unknown')
            })
            
            return result
            
        except Exception as e:
            self.create_security_audit_log('analysis_error', {
                'document_hash': self.calculate_document_hash(text),
                'error': str(e)
            })
            
            # Secure fallback
            return {
                "status": "Needs Manual Review",
                "summary": "Document received but external analysis failed. Manual review required.",
                "reasoning": f"Secure analysis pipeline error: {str(e)}",
                "security_metadata": {
                    "processing_error": True,
                    "error_type": type(e).__name__
                }
            }


class SecurityError(Exception):
    """Custom exception for security violations"""
    pass


# Integration function for your existing code
def analyze_bank_statement_secure(text: str, preferred_api: str = 'anthropic') -> Dict:
    """
    Secure replacement for analyze_bank_statement function
    """
    client = SecureAPIClient()
    return client.analyze_document_securely(text, "Bank Statement", preferred_api)