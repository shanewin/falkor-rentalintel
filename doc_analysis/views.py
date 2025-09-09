import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .utils import extract_text_and_metadata, analyze_bank_statement, analyze_pay_stub, detect_pdf_modifications

import logging
logging.basicConfig(level=logging.DEBUG)


@csrf_exempt
def analyze_document(request):
    """API endpoint to analyze uploaded PDFs."""
    if request.method == "POST" and request.FILES.get("file"):
        uploaded_file = request.FILES["file"]

        # Save file temporarily
        file_path = f"/tmp/{uploaded_file.name}"
        with open(file_path, "wb") as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        # Extract data
        pdf_data = extract_text_and_metadata(file_path)

        # Choose analysis based on document type
        doc_type = request.POST.get("document_type")
        if doc_type == "Bank Statement":
            analysis_result = analyze_bank_statement(pdf_data["text"])
        elif doc_type == "Pay Stub":
            analysis_result = analyze_pay_stub(pdf_data["text"])
        else:
            analysis_result = "No specific analysis available."

        # Detect modifications
        modification_check = detect_pdf_modifications(pdf_data["metadata"])

        # Cleanup
        os.remove(file_path)

        return JsonResponse({
            "analysis": analysis_result,
            "modification_check": modification_check,
        })

    return JsonResponse({"error": "Invalid request"}, status=400)
