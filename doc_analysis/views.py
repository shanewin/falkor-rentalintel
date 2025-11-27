import os
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from .utils import extract_text_and_metadata, analyze_bank_statement, analyze_pay_stub, analyze_tax_return, detect_pdf_modifications, store_document_embeddings, get_embedding_for_text
from .secure_api_client import analyze_bank_statement_secure, analyze_pay_stub_secure, analyze_tax_return_secure
from .tasks import store_document_embeddings_task
from .models import DocumentEmbedding

from django.db import connection

import logging
logging.basicConfig(level=logging.DEBUG)


@csrf_protect
@login_required
@require_POST
def analyze_document(request):
    """API endpoint to analyze uploaded PDFs."""
    # Permission gate
    if not request.user.has_perm("doc_analysis.can_analyze_documents"):
        return JsonResponse(
            {
                "status": "error",
                "reasoning": "You are not authorized to analyze documents",
            },
            status=403
        )

    # User-based rate limiting (configurable via env)
    limit = int(os.getenv("DOC_ANALYSIS_RATE_LIMIT", "30"))  # requests
    window = int(os.getenv("DOC_ANALYSIS_RATE_WINDOW", "60"))  # seconds
    client_id = f"user:{request.user.id}"
    cache_key = f"doc_analysis:rl:{client_id}"
    try:
        current = cache.incr(cache_key)
    except ValueError:
        cache.add(cache_key, 1, timeout=window)
        current = 1

    if current > limit:
        return JsonResponse(
            {
                "status": "error",
                "reasoning": "Rate limit exceeded",
                "retry_after": window
            },
            status=429
        )

    if request.FILES.get("file"):
        uploaded_file = request.FILES["file"]

        # Save file temporarily
        file_path = f"/tmp/{uploaded_file.name}"
        with open(file_path, "wb") as f:
            for chunk in uploaded_file.chunks():
                f.write(chunk)

        # Extract data
        pdf_data = extract_text_and_metadata(file_path)

        # Prefer full_text; fall back to joined chunks to avoid missing key errors
        extracted_text = pdf_data.get("full_text") or "\n".join(pdf_data.get("text_chunks", []))

        # Store embeddings asynchronously; best effort, skip on errors
        text_chunks = pdf_data.get("text_chunks") or []
        try:
            store_document_embeddings_task.delay(uploaded_file.name, text_chunks)
        except Exception:
            # Fallback to synchronous best-effort if Celery not running
            store_document_embeddings(uploaded_file.name, text_chunks)

        # Choose analysis based on document type
        doc_type = request.POST.get("document_type")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        preferred_api = "anthropic" if anthropic_key else ("openai" if openai_key else None)

        if doc_type == "Bank Statement":
            if not preferred_api:
                return JsonResponse(
                    {
                        "status": "Needs Manual Review",
                        "reasoning": "LLM analysis unavailable: ANTHROPIC_API_KEY or OPENAI_API_KEY is required",
                    },
                    status=503
                )
            # Always use the secure redaction + LLM flow
            analysis_result = analyze_bank_statement_secure(extracted_text, preferred_api)
        elif doc_type == "Pay Stub":
            if not preferred_api:
                return JsonResponse(
                    {
                        "status": "Needs Manual Review",
                        "reasoning": "LLM analysis unavailable: ANTHROPIC_API_KEY or OPENAI_API_KEY is required",
                    },
                    status=503
                )
            analysis_result = analyze_pay_stub_secure(extracted_text, preferred_api)
        elif doc_type == "Tax Return":
            if not preferred_api:
                return JsonResponse(
                    {
                        "status": "Needs Manual Review",
                        "reasoning": "LLM analysis unavailable: ANTHROPIC_API_KEY or OPENAI_API_KEY is required",
                    },
                    status=503
                )
            analysis_result = analyze_tax_return_secure(extracted_text, preferred_api)
        else:
            return JsonResponse(
                {
                    "status": "error",
                    "reasoning": f"Unsupported document type: {doc_type or 'None provided'}",
                },
                status=400
            )

        # Detect modifications (metadata + lightweight content fingerprints)
        modification_check = detect_pdf_modifications(pdf_data["metadata"], file_path=file_path)
        tampering_suspected = None
        tampering_severity = None
        if isinstance(modification_check, dict):
            tampering_suspected = modification_check.get("tampering_suspected")
            tampering_severity = modification_check.get("severity")

        # Attach modification info to the analysis result when it's a dict
        if isinstance(analysis_result, dict):
            analysis_result["modification_check"] = modification_check

        # Cleanup
        os.remove(file_path)

        return JsonResponse({
            "analysis": analysis_result,
            "modification_check": modification_check,
            "tampering_suspected": tampering_suspected,
            "tampering_severity": tampering_severity,
        })

    return JsonResponse(
        {
            "status": "error",
            "reasoning": "Invalid request: POST with a file is required",
        },
        status=400
    )


@csrf_protect
@login_required
@require_POST
def search_embeddings(request):
    """
    Simple semantic search over stored document embeddings.
    """
    if not request.user.has_perm("doc_analysis.can_analyze_documents"):
        return JsonResponse(
            {
                "status": "error",
                "reasoning": "You are not authorized to search document embeddings",
            },
            status=403
        )

    query = request.POST.get("query", "").strip()
    top_k = int(request.POST.get("k", "5"))
    top_k = min(max(top_k, 1), 20)

    if not query:
        return JsonResponse(
            {
                "status": "error",
                "reasoning": "Query text is required",
            },
            status=400
        )

    embedding = get_embedding_for_text(query)
    if not embedding:
        return JsonResponse(
            {
                "status": "error",
                "reasoning": "Embedding model unavailable",
            },
            status=503
        )

    # Use raw SQL with pgvector cosine distance
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT id, file_name, content, 1 - (embedding <#> %s::vector) AS similarity
            FROM doc_analysis_documentembedding
            ORDER BY embedding <#> %s::vector
            LIMIT %s
            """,
            [embedding, embedding, top_k],
        )
        rows = cursor.fetchall()

    results = [
        {
            "id": row[0],
            "file_name": row[1],
            "content": row[2],
            "similarity": float(row[3]),
        }
        for row in rows
    ]

    return JsonResponse(
        {
            "status": "ok",
            "results": results,
        }
    )


@csrf_protect
@login_required
def search_embeddings_ui(request):
    """
    Minimal UI wrapper around embedding search.
    """
    context = {
        "results": None,
        "error": None,
        "query": "",
        "k": 5
    }

    if not request.user.has_perm("doc_analysis.can_analyze_documents"):
        context["error"] = "You are not authorized to search document embeddings"
        return render(request, "doc_analysis/search.html", context, status=403)

    if request.method == "POST":
        query = request.POST.get("query", "").strip()
        k = request.POST.get("k", "5")
        context["query"] = query
        try:
            k_int = int(k)
        except ValueError:
            k_int = 5
        k_int = min(max(k_int, 1), 20)
        context["k"] = k_int

        if not query:
            context["error"] = "Query text is required"
            return render(request, "doc_analysis/search.html", context, status=400)

        embedding = get_embedding_for_text(query)
        if not embedding:
            context["error"] = "Embedding model unavailable"
            return render(request, "doc_analysis/search.html", context, status=503)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, file_name, content, 1 - (embedding <#> %s::vector) AS similarity
                FROM doc_analysis_documentembedding
                ORDER BY embedding <#> %s::vector
                LIMIT %s
                """,
                [embedding, embedding, k_int],
            )
            rows = cursor.fetchall()

        context["results"] = [
            {
                "id": row[0],
                "file_name": row[1],
                "content": row[2],
                "similarity": float(row[3]),
            }
            for row in rows
        ]

    return render(request, "doc_analysis/search.html", context)
