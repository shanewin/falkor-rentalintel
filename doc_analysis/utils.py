import pdfplumber
import fitz  # PyMuPDF
import pytesseract
import requests
import json
from pdf2image import convert_from_path
try:
    import magic
except ImportError:
    magic = None
from pydantic import BaseModel, Field
from typing_extensions import Literal, Optional
# import ollama  # Removed - using external APIs or basic fallback
import re
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain_ollama import OllamaEmbeddings  # Removed - not using local embeddings
import numpy as np
from psycopg2.extras import execute_values
import hashlib
import os

try:
    import openai
except ImportError:
    openai = None



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
        
        if os.getenv("DOC_ANALYSIS_DEBUG") == "1":
            print(f"DEBUG: PDF has {page_count} pages")
        
        for page_num in range(page_count):
            page = doc[page_num]
            page_text = page.get_text()
            if page_text.strip():
                full_text += f"\n--- PAGE {page_num + 1} ---\n"
                full_text += page_text
                if os.getenv("DOC_ANALYSIS_DEBUG") == "1":
                    print(f"DEBUG: Page {page_num + 1} extracted {len(page_text)} characters")
        
        # If PyMuPDF extraction is poor, try LangChain as backup
        if len(full_text.strip()) < 500:  # Very little text extracted
            if os.getenv("DOC_ANALYSIS_DEBUG") == "1":
                print("DEBUG: PyMuPDF extraction poor, trying LangChain PyPDFLoader")
            loader = PyPDFLoader(pdf_path)
            pages = loader.load()
            full_text = "\n".join([f"\n--- PAGE {i+1} ---\n{page.page_content}" for i, page in enumerate(pages)])
        
        # If still poor, try pdfplumber
        if len(full_text.strip()) < 500:
            if os.getenv("DOC_ANALYSIS_DEBUG") == "1":
                print("DEBUG: LangChain extraction poor, trying pdfplumber")
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                full_text = ""
                for i, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        full_text += f"\n--- PAGE {i+1} ---\n"
                        full_text += page_text

        if os.getenv("DOC_ANALYSIS_DEBUG") == "1":
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
        # ✅ Detect file type (to check for tampering)
        if magic:
            data["file_type"] = magic.from_file(pdf_path, mime=True)
        else:
            data["file_type"] = "application/pdf"  # Fallback

        doc.close()

    except Exception as e:
        if os.getenv("DOC_ANALYSIS_DEBUG") == "1":
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
    """
    Basic rule-based analysis for tax returns (e.g., Form 1040).
    Looks for key elements: form identifiers, filer info, income lines, and signatures.
    """
    text_lower = text.lower()

    # Key elements to look for
    has_form = any(keyword in text_lower for keyword in ['form 1040', 'form 1040-sr', 'form 1040ez', 'schedule'])
    has_filer_info = any(keyword in text_lower for keyword in ['social security number', 'ssn', 'spouse', 'filing status', 'single', 'married'])
    has_income_lines = any(keyword in text_lower for keyword in ['wages', 'agi', 'adjusted gross income', 'taxable income', 'total income'])
    has_signature = any(keyword in text_lower for keyword in ['sign here', 'signature of taxpayer', 'taxpayer signature'])
    has_year = bool(re.search(r'20\d{2}', text))

    found = [has_form, has_filer_info, has_income_lines, has_signature, has_year]
    count = sum(found)

    missing = []
    if not has_form: missing.append("form identifier (e.g., Form 1040)")
    if not has_filer_info: missing.append("filer information")
    if not has_income_lines: missing.append("income/AGI lines")
    if not has_signature: missing.append("signatures")
    if not has_year: missing.append("tax year")

    if count >= 4:
        status = "Complete"
        summary = "Tax return appears complete with form ID, filer info, income lines, and signatures."
        reasoning = "Most core sections for a Form 1040 are present."
    elif count >= 2:
        status = "Not Complete"
        summary = f"Tax return is missing key sections: {', '.join(missing[:3])}."
        reasoning = "Some required sections are absent or unclear."
    else:
        status = "Needs Manual Review"
        summary = "Document does not look like a standard tax return or is heavily incomplete."
        reasoning = "Too few recognizable tax return elements found."

    return {
        "status": status,
        "summary": summary,
        "reasoning": reasoning + " (Basic tax return analysis)",
        "modification_check": "Not assessed for tax returns"
    }


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


def detect_pdf_modifications(metadata, file_path=None, max_pages: int = 20):
    """
    Checks for possible PDF tampering using metadata and lightweight content fingerprints.
    
    Returns a dict with metadata comparison, page hashes, content sizes, and object counts.
    """
    result = {
        "metadata_check": "No modification metadata found.",
        "tampering_suspected": None,
        "page_fingerprints": [],
        "object_summary": {},
        "notes": []
    }

    # Metadata-based check
    if metadata.get("modDate") and metadata.get("creationDate"):
        tamper_flag = metadata["creationDate"] != metadata["modDate"]
        result["metadata_check"] = f"Created: {metadata['creationDate']}, Modified: {metadata['modDate']}"
        result["tampering_suspected"] = bool(tamper_flag)
        if tamper_flag:
            result["severity"] = "medium"
    elif metadata.get("modDate") or metadata.get("creationDate"):
        result["metadata_check"] = "Partial metadata present (creation or mod date only)"

    # Content-based checks (best-effort)
    if file_path:
        try:
            doc = fitz.open(file_path)
            page_fingerprints = []
            total_images = 0
            total_xobjects = 0
            total_content_bytes = 0
            xref_length = getattr(doc, "xref_length", lambda: None)() if callable(getattr(doc, "xref_length", None)) else None
            is_encrypted = getattr(doc, "is_encrypted", False)
            is_repaired = getattr(doc, "is_repaired", None)  # Some versions expose this

            for page in doc:
                if page.number >= max_pages:
                    result["notes"].append(f"Page fingerprinting truncated at {max_pages} pages")
                    break
                text = page.get_text() or ""
                text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
                images = page.get_images(full=True)
                total_images += len(images)
                # Count XObjects (images + other streams)
                xobjects = page.get_xobjects()
                total_xobjects += len(xobjects) if xobjects else 0
                # Content stream lengths / hash
                contents = page.get_contents()
                if contents:
                    if isinstance(contents, (bytes, bytearray)):
                        content_bytes = contents
                    else:
                        content_bytes = b"".join([c if isinstance(c, (bytes, bytearray)) else b"" for c in contents])
                else:
                    content_bytes = b""
                total_content_bytes += len(content_bytes)
                content_hash = hashlib.sha256(content_bytes).hexdigest()[:16] if content_bytes else "none"

                page_fingerprints.append({
                    "page": page.number + 1,
                    "text_hash": text_hash,
                    "image_count": len(images),
                    "xobject_count": len(xobjects) if xobjects else 0,
                    "content_hash": content_hash,
                    "content_bytes": len(content_bytes),
                    "size": {"width": page.rect.width, "height": page.rect.height}
                })

            result["page_fingerprints"] = page_fingerprints
            result["object_summary"] = {
                "total_images": total_images,
                "total_xobjects": total_xobjects,
                "total_content_bytes": total_content_bytes,
                "page_count": len(doc),
                "xref_length": xref_length,
                "is_encrypted": is_encrypted,
                "is_repaired": is_repaired
            }
            # Simple heuristic: if multiple pages have identical text hash but different content hash,
            # flag as potentially modified (e.g., swapped content/overlay)
            if page_fingerprints:
                seen_text = {}
                for fp in page_fingerprints:
                    key = fp["text_hash"]
                    if key in seen_text and seen_text[key] != fp["content_hash"]:
                        result["notes"].append(
                            f"Identical text hash with different content hash on pages {seen_text[key]} and {fp['page']}"
                        )
                        result["tampering_suspected"] = True if result["tampering_suspected"] is None else result["tampering_suspected"]
                        result["severity"] = result.get("severity") or "medium"
                    else:
                        seen_text[key] = fp["content_hash"]

            doc.close()
        except Exception as e:
            result["object_summary"] = {"error": f"Content fingerprinting failed: {str(e)}"}

    # Final severity/tampering defaulting
    if result["tampering_suspected"] is None:
        result["tampering_suspected"] = False
        result["severity"] = result.get("severity") or "low"
    else:
        result["severity"] = result.get("severity") or ("low" if not result["tampering_suspected"] else "medium")

    return result


def store_document_embeddings(file_name: str, text_chunks, max_chunks: int = 20) -> dict:
    """
    Generate and persist embeddings for text chunks using OpenAI embeddings.
    Returns a status dict; no-op if OpenAI client not configured.
    """
    if os.getenv("DOC_ANALYSIS_SKIP_EXTERNAL") == "1":
        return {"status": "skipped", "reason": "External calls disabled (DOC_ANALYSIS_SKIP_EXTERNAL)"}
    if not openai:
        return {"status": "skipped", "reason": "openai package not available"}

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"status": "skipped", "reason": "OPENAI_API_KEY not set"}

    from .models import DocumentEmbedding

    chunks = list(text_chunks or [])
    if not chunks:
        return {"status": "skipped", "reason": "No text chunks to embed"}

    # Trim to avoid excessive calls
    chunks = chunks[:max_chunks]

    expected_dim = int(os.getenv("OPENAI_EMBEDDING_DIM", "1536"))

    try:
        client = openai.OpenAI(api_key=api_key) if hasattr(openai, "OpenAI") else openai
        # Build request for embeddings
        if hasattr(client, "embeddings"):
            resp = client.embeddings.create(
                model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                input=chunks,
            )
            vectors = [data["embedding"] for data in resp["data"]] if isinstance(resp, dict) else [item.embedding for item in resp.data]
        else:
            resp = client.Embeddings.create(
                model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                input=chunks,
            )
            vectors = [item["embedding"] for item in resp["data"]]

        # Validate dimensions
        if any(len(vec) != expected_dim for vec in vectors):
            return {
                "status": "failed",
                "reason": f"Embedding dimension mismatch (expected {expected_dim}, got {[len(v) for v in vectors]})"
            }

        docs = []
        for chunk, vec in zip(chunks, vectors):
            docs.append(
                DocumentEmbedding(
                    file_name=file_name,
                    content=chunk,
                    embedding=vec
                )
            )

        # Optional: remove old embeddings for this file to avoid duplicates
        DocumentEmbedding.objects.filter(file_name=file_name).delete()
        DocumentEmbedding.objects.bulk_create(docs)

        return {"status": "stored", "count": len(docs)}
    except Exception as e:
        return {"status": "failed", "reason": str(e)}


def get_embedding_for_text(text: str):
    """
    Get a single embedding vector for the provided text using OpenAI.
    Returns list[float] or None.
    """
    if os.getenv("DOC_ANALYSIS_SKIP_EXTERNAL") == "1":
        return None
    if not openai:
        return None
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    expected_dim = int(os.getenv("OPENAI_EMBEDDING_DIM", "1536"))

    try:
        client = openai.OpenAI(api_key=api_key) if hasattr(openai, "OpenAI") else openai
        if hasattr(client, "embeddings"):
            resp = client.embeddings.create(
                model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                input=text,
            )
            emb = resp["data"][0]["embedding"] if isinstance(resp, dict) else resp.data[0].embedding
        else:
            resp = client.Embeddings.create(
                model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
                input=text,
            )
            emb = resp["data"][0]["embedding"]
        if len(emb) != expected_dim:
            return None
        return emb
    except Exception:
        return None
