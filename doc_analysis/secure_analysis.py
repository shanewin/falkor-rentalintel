"""
Secure document analysis with redaction for external APIs
"""
from .redaction_utils import DocumentRedactor, check_for_remaining_sensitive_data
from .replicate_utils import analyze_bank_statement_replicate
from .utils import analyze_bank_statement
import json
import logging
import re
import os
from django.utils import timezone

logger = logging.getLogger(__name__)


def analyze_document_securely(text: str, document_type: str, use_external_api: bool = True):
    """
    Analyze document with appropriate security measures.
    
    Args:
        text: Document text to analyze
        document_type: Type of document (Bank Statement, Pay Stub, etc.)
        use_external_api: Whether to use Replicate (True) or local Ollama (False)
    
    Returns:
        Analysis results dict
    """
    
    # Step 1: Check document sensitivity level
    sensitivity_level = determine_sensitivity(text, document_type)
    
    if sensitivity_level == "HIGH" and use_external_api:
        # For highly sensitive docs, force basic processing
        logger.info("High sensitivity document detected - using basic analysis")
        return analyze_bank_statement(text)
    
    if use_external_api:
        # Step 2: Redact sensitive information
        redactor = DocumentRedactor()
        redacted_text, redaction_map = redactor.redact_document(text)
        
        # Step 3: Final safety check
        remaining_issues = check_for_remaining_sensitive_data(redacted_text)
        if remaining_issues:
            logger.warning(f"Sensitive data may remain: {remaining_issues}")
            # Fall back to basic processing
            return analyze_bank_statement(text)
        
        # Step 4: Send to external API
        try:
            # Log what we're sending (without the actual content)
            logger.info(f"Sending redacted document to Replicate. Redacted {len(redaction_map)} items")
            
            # Analyze with external API
            result = analyze_bank_statement_replicate(redacted_text)
            
            # Step 5: Restore any redacted tokens in the response
            if result.get('summary'):
                result['summary'] = redactor.restore_redacted(result['summary'])
            
            # Add security notice
            result['security_note'] = f"Analyzed with redaction. {len(redaction_map)} items were redacted."
            
            return result
            
        except Exception as e:
            logger.error(f"External API failed: {e}")
            # Fall back to basic processing
            return analyze_bank_statement(text)
    
    else:
        # Basic processing - no redaction needed
        return analyze_bank_statement(text)


def determine_sensitivity(text: str, document_type: str) -> str:
    """
    Determine document sensitivity level.
    
    Returns:
        "HIGH", "MEDIUM", or "LOW"
    """
    high_sensitivity_indicators = [
        r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',  # SSN
        r'tax\s*return',                       # Tax documents
        r'medical',                            # Medical records
        r'confidential',                       # Marked confidential
        r'do\s*not\s*share',                  # Privacy notices
    ]
    
    medium_sensitivity_indicators = [
        r'account\s*number',
        r'routing\s*number',
        r'salary',
        r'income',
    ]
    
    # Check for high sensitivity
    for pattern in high_sensitivity_indicators:
        if re.search(pattern, text, re.IGNORECASE):
            return "HIGH"
    
    # Check for medium sensitivity
    for pattern in medium_sensitivity_indicators:
        if re.search(pattern, text, re.IGNORECASE):
            return "MEDIUM"
    
    return "LOW"


# Integration with your Celery task
def analyze_with_smart_routing(uploaded_file, text):
    """
    Smart routing between local and external processing based on:
    - Document sensitivity
    - System load
    - Cost considerations
    """
    
    # Check if external API is enabled (from settings)
    use_external = os.environ.get('USE_EXTERNAL_API', 'false').lower() == 'true'
    
    # Check current queue depth
    from celery import current_app
    active_tasks = current_app.control.inspect().active()
    queue_depth = sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0
    
    # Decision logic
    if queue_depth > 10 and use_external:
        # High load - use external API for faster processing
        logger.info(f"High queue depth ({queue_depth}) - using external API")
        return analyze_document_securely(text, uploaded_file.document_type, use_external_api=True)
    else:
        # Normal load - use local processing
        return analyze_document_securely(text, uploaded_file.document_type, use_external_api=False)


# Audit logging for compliance
def log_document_processing(user, document_type, used_external_api, redaction_count):
    """
    Create audit log for compliance tracking.
    """
    from applications.models import ProcessingAuditLog  # You'd need to create this model
    
    ProcessingAuditLog.objects.create(
        user=user,
        document_type=document_type,
        processing_method="external_api" if used_external_api else "local",
        redaction_count=redaction_count,
        timestamp=timezone.now()
    )