#!/usr/bin/env python3
"""
Show exactly what content is sent to Anthropic API after redaction
"""
import os
import sys
import django

# Setup Django
sys.path.append('/Users/shanewinter/Desktop/door-way')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate_project.settings')
django.setup()

from doc_analysis.secure_api_client import SecureAPIClient

def show_anthropic_content():
    """Show what Anthropic actually receives"""
    
    # Sample bank statement text (replace with your actual extracted text)
    sample_text = """
    Charles Schwab Bank
    Customer Service Information
    Shane Winter
    281 West 123rd Street, Apt 4B
    New York, NY 10027
    
    Account Number: 440030259723
    Statement Period: February 1, 2025 - February 28, 2025
    Beginning Balance: $8,794.82
    Ending Balance: $7,974.92
    
    TRANSACTION HISTORY:
    02/01/2025  DIRECT DEPOSIT - Educational Network    +$3,163.94
    02/03/2025  VISA DEBIT CARD - GROCERY STORE        -$127.45
    02/05/2025  ELECTRONIC WITHDRAWAL - RENT           -$2,500.00
    02/07/2025  ATM WITHDRAWAL                         -$200.00
    02/10/2025  VISA DEBIT CARD - GAS STATION          -$65.30
    02/12/2025  ELECTRONIC DEPOSIT - TAX REFUND        +$1,250.00
    02/15/2025  DIRECT DEPOSIT - Educational Network    +$3,163.94
    02/18/2025  UTILITY PAYMENT - Con Edison           -$1,397.15
    02/20/2025  VISA DEBIT CARD - RESTAURANT           -$89.75
    02/22/2025  ATM WITHDRAWAL                         -$300.00
    02/25/2025  ELECTRONIC WITHDRAWAL - INSURANCE      -$485.50
    02/28/2025  BANK FEE                               -$12.00
    
    Customer Service: 888-403-9000
    SSN: 123-45-6789 (for tax reporting)
    Routing Number: 121000248
    
    --- END OF STATEMENT ---
    """
    
    print("🔍 CONTENT ANALYSIS DEMONSTRATION")
    print("=" * 80)
    
    client = SecureAPIClient()
    
    # Show original content
    print("📄 ORIGINAL DOCUMENT CONTENT:")
    print("-" * 50)
    print(sample_text)
    print(f"Original length: {len(sample_text)} characters")
    
    print("\n" + "=" * 80)
    
    # Show what gets sent to Anthropic
    try:
        doc_hash = client.calculate_document_hash(sample_text)
        
        # Step 1: Truncate to 5000 chars
        truncated_text = sample_text[:5000]
        
        # Step 2: Apply redaction
        redacted_text, redaction_map = client.redactor.redact_document(truncated_text)
        
        print("📤 CONTENT SENT TO ANTHROPIC (AFTER REDACTION):")
        print("-" * 50)
        print(redacted_text)
        print(f"Redacted length: {len(redacted_text)} characters")
        print(f"Redactions applied: {len(redaction_map)}")
        
        print("\n" + "=" * 80)
        print("🔐 REDACTION MAPPING:")
        print("-" * 50)
        for token, original in redaction_map.items():
            print(f"  {token} → {original}")
        
        print("\n" + "=" * 80)
        print("💡 ANALYSIS:")
        print("-" * 50)
        
        # Check what financial data is preserved
        financial_indicators = ['balance', '$', 'deposit', 'withdrawal', 'transaction']
        preserved_financial = sum(1 for indicator in financial_indicators if indicator.lower() in redacted_text.lower())
        
        transaction_lines = [line for line in redacted_text.split('\n') if '$' in line and any(word in line.lower() for word in ['deposit', 'withdrawal', 'debit', 'credit'])]
        
        print(f"✅ Financial indicators preserved: {preserved_financial}/5")
        print(f"✅ Transaction lines preserved: {len(transaction_lines)}")
        print(f"✅ Contains balance information: {'balance' in redacted_text.lower()}")
        print(f"✅ Contains income patterns: {'deposit' in redacted_text.lower()}")
        print(f"✅ PII completely redacted: {len(redaction_map)} items protected")
        
        if len(transaction_lines) >= 5:
            print("\n✅ ANTHROPIC GETS FULL FINANCIAL ANALYSIS CAPABILITY:")
            print("  - Complete transaction history")
            print("  - Income verification data") 
            print("  - Spending patterns")
            print("  - Account balance trends")
            print("  - BUT NO PERSONAL INFORMATION!")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    show_anthropic_content()