from celery import shared_task
from django.core.files.storage import default_storage
import tempfile
import os
from doc_analysis.utils import extract_text_and_metadata, analyze_bank_statement, detect_pdf_modifications
from doc_analysis.secure_api_client import analyze_bank_statement_secure
import json


@shared_task(bind=True)
def analyze_document_async(self, uploaded_file_id):
    """
    Asynchronous task to analyze uploaded documents using Ollama.
    This prevents the web request from timing out during long AI analysis.
    """
    try:
        from applications.models import UploadedFile
        
        # Get the uploaded file record
        try:
            uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
        except UploadedFile.DoesNotExist:
            return {"error": "Uploaded file not found"}
        
        # Update task status to indicate processing has started
        self.update_state(
            state='PROGRESS',
            meta={'status': 'Starting document analysis...', 'progress': 10}
        )
        
        # Download file to temporary location for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            # Download file content from Cloudinary URL
            import requests
            response = requests.get(uploaded_file.file.url, stream=True)
            response.raise_for_status()
            
            for chunk in response.iter_content(chunk_size=8192):
                temp_file.write(chunk)
            temp_file_path = temp_file.name
        
        try:
            # Update progress
            self.update_state(
                state='PROGRESS',
                meta={'status': 'Extracting text from document...', 'progress': 30}
            )
            
            # Extract text and metadata
            extracted_data = extract_text_and_metadata(temp_file_path)
            
            if "error" in extracted_data:
                return {
                    "status": "Needs Manual Review",
                    "summary": "Failed to extract text from document",
                    "reasoning": extracted_data["error"],
                    "modification_check": "Text extraction failed"
                }
            
            # Update progress
            self.update_state(
                state='PROGRESS',
                meta={'status': 'Running AI analysis...', 'progress': 60}
            )
            
            # Use more text for better analysis (up to 5000 characters for external API)
            text_chunks = extracted_data.get("text_chunks", [])
            full_text = extracted_data.get("full_text", "")
            
            # Use more text for external APIs, less for basic fallback
            if os.getenv('ANTHROPIC_API_KEY') or os.getenv('OPENAI_API_KEY'):
                max_chars = 5000
                max_chunks = 5
            else:
                # Basic fallback analysis works better with less text
                max_chars = 1500
                max_chunks = 2
            
            limited_text = ""
            if full_text and len(full_text) > 100:
                # Use full text up to max_chars
                limited_text = full_text[:max_chars]
            else:
                # Fallback to chunks method
                for chunk in text_chunks[:max_chunks]:
                    if len(limited_text + chunk) > max_chars:
                        break
                    limited_text += chunk + "\n"
            
            if not limited_text.strip():
                limited_text = "No readable text found in document"
            
            # Check for PDF modifications
            metadata = extracted_data.get("metadata", {})
            modification_check = detect_pdf_modifications(metadata)
            
            # Analyze based on document type
            if uploaded_file.document_type == "Bank Statement":
                # Try secure external API first (if API keys are configured)
                try:
                    if os.getenv('ANTHROPIC_API_KEY') or os.getenv('OPENAI_API_KEY'):
                        preferred_api = 'anthropic' if os.getenv('ANTHROPIC_API_KEY') else 'openai'
                        analysis_result = analyze_bank_statement_secure(limited_text, preferred_api)
                        # Add modification check to the result
                        analysis_result["modification_check"] = modification_check
                    else:
                        # Fall back to basic rule-based analysis
                        analysis_result = analyze_bank_statement(limited_text)
                        # Add modification check to the result
                        analysis_result["modification_check"] = modification_check
                except Exception as e:
                    # If secure API fails, fall back to local analysis
                    analysis_result = analyze_bank_statement(limited_text)
                    # Add modification check to the result
                    analysis_result["modification_check"] = modification_check
                    # Add note about fallback
                    if "reasoning" in analysis_result:
                        analysis_result["reasoning"] += f" (Fallback: External API failed - {str(e)[:100]})"
            else:
                # For other document types, provide a generic response for now
                analysis_result = {
                    "status": "Needs Manual Review",
                    "summary": f"Document type '{uploaded_file.document_type}' uploaded successfully",
                    "reasoning": "Automatic analysis is currently only available for Bank Statements. Other document types require manual review.",
                    "modification_check": modification_check
                }
            
            # Update progress
            self.update_state(
                state='PROGRESS',
                meta={'status': 'Saving analysis results...', 'progress': 90}
            )
            
            # Save analysis results to database
            uploaded_file.analysis_results = json.dumps(analysis_result)
            uploaded_file.save()
            
            # Final success state
            self.update_state(
                state='SUCCESS',
                meta={'status': 'Analysis complete', 'progress': 100}
            )
            
            return analysis_result
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except Exception as e:
        # Handle any unexpected errors
        error_result = {
            "status": "Needs Manual Review",
            "summary": "Document analysis failed due to system error",
            "reasoning": f"An unexpected error occurred during analysis: {str(e)}",
            "modification_check": "Manual review required due to system error"
        }
        
        # Try to save error result to database
        try:
            from applications.models import UploadedFile
            uploaded_file = UploadedFile.objects.get(id=uploaded_file_id)
            uploaded_file.analysis_results = json.dumps(error_result)
            uploaded_file.save()
        except:
            pass  # If we can't save, at least return the error
        
        return error_result


@shared_task
def cleanup_old_analysis_tasks():
    """
    Periodic task to clean up old analysis results or tasks if needed.
    This can be scheduled to run daily to maintain system performance.
    """
    # This could be used to clean up old temporary files or completed tasks
    # For now, it's a placeholder for future cleanup operations
    return "Cleanup completed"