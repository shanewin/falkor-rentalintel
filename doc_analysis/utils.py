import pdfplumber
import fitz  # PyMuPDF
import pytesseract
import requests
import json
from pdf2image import convert_from_path
import magic
from pydantic import BaseModel, Field
from typing_extensions import Literal, Optional
# import ollama  # Removed - using external APIs or basic fallback
import re
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain_ollama import OllamaEmbeddings  # Removed - not using local embeddings
import numpy as np
from psycopg2.extras import execute_values



from django.db import connection


# Ollama configuration removed - using external APIs or basic fallback
# External APIs (Anthropic/OpenAI) are configured via environment variables


def extract_text_and_metadata(pdf_path):
    """Extracts text, metadata, and file type from a PDF using multiple methods for best results."""

    data = {}

    try:
        # Method 1: Try PyMuPDF first (often better for bank statements)
        doc = fitz.open(pdf_path)
        full_text = ""
        page_count = len(doc)
        
        print(f"DEBUG: PDF has {page_count} pages")
        
        for page_num in range(page_count):
            page = doc[page_num]
            page_text = page.get_text()
            if page_text.strip():
                full_text += f"\n--- PAGE {page_num + 1} ---\n"
                full_text += page_text
                print(f"DEBUG: Page {page_num + 1} extracted {len(page_text)} characters")
        
        # If PyMuPDF extraction is poor, try LangChain as backup
        if len(full_text.strip()) < 500:  # Very little text extracted
            print("DEBUG: PyMuPDF extraction poor, trying LangChain PyPDFLoader")
            loader = PyPDFLoader(pdf_path)
            pages = loader.load()
            full_text = "\n".join([f"\n--- PAGE {i+1} ---\n{page.page_content}" for i, page in enumerate(pages)])
        
        # If still poor, try pdfplumber
        if len(full_text.strip()) < 500:
            print("DEBUG: LangChain extraction poor, trying pdfplumber")
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                full_text = ""
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        full_text += f"\n--- PAGE {i+1} ---\n"
                        full_text += page_text

        print(f"DEBUG: Final extracted text length: {len(full_text)} characters")
        print(f"DEBUG: First 500 chars: {full_text[:500]}")

        # ✅ Chunk text for embeddings
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200)
        text_chunks = text_splitter.split_text(full_text)

        data["text_chunks"] = text_chunks if text_chunks else ["No text found."]
        data["full_text"] = full_text  # Add full text for debugging
        data["page_count"] = page_count

        # ✅ Extract metadata using PyMuPDF
        data["metadata"] = doc.metadata or {}

        # ✅ Detect file type (to check for tampering)
        data["file_type"] = magic.from_file(pdf_path, mime=True)

        doc.close()

    except Exception as e:
        print(f"DEBUG: Error in text extraction: {str(e)}")
        data["error"] = f"Error processing PDF: {str(e)}"
    
    return data


def extract_json(text):
    """Extracts valid JSON from text and removes unnecessary formatting like triple backticks."""
    text = text.strip().strip("`")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    return match.group() if match else text


# ✅ Define the output schema using Pydantic
class BankStatementAnalysis(BaseModel):
    status: Literal["Complete", "Not Complete", "Needs Manual Review"]  # ✅ Strict values
    summary: str  # Short summary for the landlord
    reasoning: str  # Explanation if incomplete or needs review


def analyze_bank_statement(text):
    """
    Analyzes a bank statement using basic rule-based analysis.
    This is the fallback when external APIs (Anthropic/OpenAI) are not available.
    """
    # Always use the basic analysis as fallback since Ollama is removed
    return provide_basic_analysis(text)


def analyze_pay_stub(text):
    """
    Analyzes a pay stub using basic rule-based analysis.
    This is the fallback when external APIs are not available.
    """
    # Use basic analysis for pay stubs as well
    text_lower = text.lower()
    
    # Check for pay stub elements
    has_employer = any(keyword in text_lower for keyword in ['employer', 'company', 'from:'])
    has_employee = any(keyword in text_lower for keyword in ['employee', 'name:', 'to:'])
    has_pay_period = any(keyword in text_lower for keyword in ['pay period', 'period ending', 'pay date'])
    has_earnings = any(keyword in text_lower for keyword in ['earnings', 'gross pay', 'salary', 'wages'])
    has_deductions = any(keyword in text_lower for keyword in ['deductions', 'tax', 'withholding', 'net pay'])
    
    required_elements = [has_employer, has_employee, has_pay_period, has_earnings, has_deductions]
    complete_count = sum(required_elements)
    
    if complete_count >= 4:
        return "Pay stub appears complete with employer info, employee details, pay period, earnings, and deductions."
    elif complete_count >= 2:
        missing = []
        if not has_employer: missing.append("employer information")
        if not has_employee: missing.append("employee information")
        if not has_pay_period: missing.append("pay period")
        if not has_earnings: missing.append("earnings")
        if not has_deductions: missing.append("deductions")
        return f"Pay stub is missing: {', '.join(missing)}"
    else:
        return "Document does not appear to be a valid pay stub or is missing critical information."


def analyze_tax_return(text):
    return "Tax Return analysis is not implemented yet."


def provide_basic_analysis(text):
    """
    Provides basic rule-based analysis when AI is unavailable.
    Looks for common patterns in bank statements without AI.
    """
    text_lower = text.lower()
    
    # Check for basic bank statement elements
    has_account_info = any(keyword in text_lower for keyword in ['account', 'checking', 'savings'])
    has_balance = any(keyword in text_lower for keyword in ['balance', 'ending balance', 'total'])
    has_bank_name = any(keyword in text_lower for keyword in ['bank', 'credit union', 'financial'])
    has_dates = bool(re.search(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}', text))
    has_amounts = bool(re.search(r'\$\d+\.?\d*', text))
    
    # Look for account holder name patterns
    name_patterns = re.findall(r'[A-Z][a-z]+ [A-Z][a-z]+', text[:500])  # First 500 chars
    potential_names = [name for name in name_patterns if len(name.split()) == 2]
    
    # Extract balance if possible
    balance_matches = re.findall(r'(?:ending|current|available)?\s*balance[:\s]*\$?([\d,]+\.?\d*)', text_lower)
    balance_info = f"Balance: ${balance_matches[0]}" if balance_matches else "Balance not clearly identified"
    
    # Determine status based on found elements
    required_elements = [has_account_info, has_balance, has_bank_name, has_dates, has_amounts]
    complete_count = sum(required_elements)
    
    if complete_count >= 4:
        status = "Complete"
        summary = f"Bank statement appears complete. {balance_info}. Contains account information, dates, and transaction amounts."
        if potential_names:
            summary += f" Account holder appears to be: {potential_names[0]}"
        reasoning = "Document contains most required elements for a bank statement"
    elif complete_count >= 2:
        status = "Not Complete"
        missing = []
        if not has_account_info: missing.append("account information")
        if not has_balance: missing.append("balance")
        if not has_bank_name: missing.append("bank name")
        if not has_dates: missing.append("dates")
        if not has_amounts: missing.append("transaction amounts")
        
        summary = f"Bank statement is missing some key information. {balance_info if balance_matches else 'Balance unclear'}."
        reasoning = f"Missing: {', '.join(missing[:3])}"  # Show first 3 missing items
    else:
        status = "Needs Manual Review"
        summary = "Document does not appear to be a standard bank statement or is heavily corrupted."
        reasoning = "Too few recognizable bank statement elements found"
    
    return {
        "status": status,
        "summary": summary,
        "reasoning": reasoning + " (Basic analysis - AI unavailable)",
        "modification_check": "Basic analysis performed due to AI service timeout"
    }


def detect_pdf_modifications(metadata):
    """Checks if a PDF has been modified after creation."""
    if metadata.get("modDate") and metadata.get("creationDate"):
        return f"Created: {metadata['creationDate']}, Modified: {metadata['modDate']}. Possible tampering: {metadata['creationDate'] != metadata['modDate']}"
    return "No modification metadata found."
