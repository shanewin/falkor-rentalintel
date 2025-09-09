#!/usr/bin/env python
"""
Test script to verify document analysis works after Ollama removal
Run this after making the changes to ensure everything still works
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'realestate.settings')
django.setup()

from doc_analysis.utils import analyze_bank_statement, analyze_pay_stub, provide_basic_analysis
from doc_analysis.secure_api_client import analyze_bank_statement_secure

def test_basic_analysis():
    """Test the basic fallback analysis"""
    print("\n" + "="*60)
    print("Testing Basic Fallback Analysis (No External APIs)")
    print("="*60)
    
    sample_text = """
    BANK OF AMERICA
    Statement Period: 01/01/2024 - 01/31/2024
    Account Number: ****1234
    
    John Doe
    123 Main Street
    New York, NY 10001
    
    Beginning Balance: $5,234.56
    Deposits: $3,500.00
    Withdrawals: $1,234.56
    Ending Balance: $7,500.00
    
    01/15/2024  Direct Deposit - Salary    $3,500.00
    01/20/2024  Debit Card Purchase        -$234.56
    01/25/2024  ATM Withdrawal             -$1,000.00
    """
    
    result = analyze_bank_statement(sample_text)
    print("\nBasic Analysis Result:")
    print(f"Status: {result.get('status')}")
    print(f"Summary: {result.get('summary')}")
    print(f"Reasoning: {result.get('reasoning')}")
    
    return result.get('status') in ['Complete', 'Not Complete', 'Needs Manual Review']

def test_external_api_analysis():
    """Test external API analysis if configured"""
    print("\n" + "="*60)
    print("Testing External API Analysis (Anthropic/OpenAI)")
    print("="*60)
    
    if not (os.getenv('ANTHROPIC_API_KEY') or os.getenv('OPENAI_API_KEY')):
        print("No external API keys configured. Skipping this test.")
        return True
    
    sample_text = """
    Charles Schwab Bank
    Statement Date: January 31, 2024
    Account: Checking ****5678
    
    Jane Smith
    456 Oak Avenue
    San Francisco, CA 94102
    
    Summary:
    Previous Balance: $10,234.56
    Total Deposits: $5,500.00
    Total Withdrawals: $2,234.56
    Current Balance: $13,500.00
    
    Transaction History:
    01/05/2024  Payroll Deposit         $3,000.00
    01/15/2024  Transfer from Savings   $2,500.00
    01/20/2024  Rent Payment           -$2,000.00
    01/25/2024  Utilities              -$234.56
    """
    
    try:
        preferred_api = 'anthropic' if os.getenv('ANTHROPIC_API_KEY') else 'openai'
        result = analyze_bank_statement_secure(sample_text, preferred_api)
        
        print(f"\nExternal API ({preferred_api}) Analysis Result:")
        print(f"Status: {result.get('status')}")
        print(f"Summary: {result.get('summary')}")
        print(f"Reasoning: {result.get('reasoning')}")
        
        if 'security_metadata' in result:
            print(f"Security: {result['security_metadata'].get('redaction_count', 0)} items redacted")
        
        return result.get('status') in ['Complete', 'Not Complete', 'Needs Manual Review']
    except Exception as e:
        print(f"External API test failed: {e}")
        print("This is expected if the API key is invalid or the service is down.")
        return False

def test_pay_stub_analysis():
    """Test pay stub analysis"""
    print("\n" + "="*60)
    print("Testing Pay Stub Analysis")
    print("="*60)
    
    sample_pay_stub = """
    ACME Corporation
    Pay Stub
    
    Employee: John Doe
    Employee ID: 12345
    Pay Period: 01/01/2024 - 01/15/2024
    Pay Date: 01/20/2024
    
    Earnings:
    Regular Hours (80 @ $50.00): $4,000.00
    Overtime (10 @ $75.00): $750.00
    Gross Pay: $4,750.00
    
    Deductions:
    Federal Tax: $950.00
    State Tax: $237.50
    Social Security: $294.50
    Medicare: $68.88
    
    Net Pay: $3,199.12
    """
    
    result = analyze_pay_stub(sample_pay_stub)
    print(f"\nPay Stub Analysis Result: {result}")
    
    return "complete" in result.lower()

def main():
    """Run all tests"""
    print("\n" + "#"*60)
    print("# Document Analysis Test Suite")
    print("# Testing after Ollama removal")
    print("#"*60)
    
    tests = [
        ("Basic Fallback Analysis", test_basic_analysis),
        ("External API Analysis", test_external_api_analysis),
        ("Pay Stub Analysis", test_pay_stub_analysis),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    print("\n" + "#"*60)
    print("# Test Results Summary")
    print("#"*60)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    all_passed = all(success for _, success in results)
    
    if all_passed:
        print("\n🎉 All tests passed! Document analysis is working correctly.")
    else:
        print("\n⚠️  Some tests failed. Please review the output above.")
        print("Note: External API tests may fail if API keys are not configured.")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)