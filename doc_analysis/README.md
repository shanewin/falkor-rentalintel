# doc_analysis app overview

## Purpose
Handles PDF ingestion and analysis for rental applications (bank statements, pay stubs, tax returns). Extracts text/metadata, runs secure redaction + LLM analysis when API keys are present, stores basic embeddings for similarity search, and exposes an API/UI for embedding queries.

## Key pieces
- `models.py`  
  - `DocumentEmbedding`: stores file name, chunk content, and a pgvector embedding (dim 1536). Permission `doc_analysis.can_analyze_documents` gates analysis/search.

- `views.py`  
  - `analyze_document` (POST `/doc_analysis/analyze/`): saves upload, extracts text/metadata, queues embeddings store, routes to secure LLM analyzers by document type, attaches tamper-check info. Auth: login + permission + CSRF + user rate limit.  
  - `search_embeddings` (POST `/doc_analysis/search/`): semantic search over stored embeddings (permissioned).  
  - `search_embeddings_ui` (GET/POST `/doc_analysis/search/ui/`): minimal UI wrapper for embedding search (permissioned).

- `urls.py`  
  - Routes for analyze, search API, and search UI.

- `utils.py`  
  - `extract_text_and_metadata`: multi-backend PDF text extraction + metadata + MIME.  
  - Rule-based analyzers (bank, pay stub, tax return).  
  - `detect_pdf_modifications`: metadata compare + per-page fingerprints + tamper flags/severity.  
  - Embedding helpers (`store_document_embeddings`, `get_embedding_for_text`) using OpenAI embeddings (dim 1536 by default).

- `secure_api_client.py`  
  - Redaction + sensitivity assessment, prepares secure payloads, calls Anthropic/OpenAI with zero-retention intent, normalizes responses by doc type, restores redaction tokens. Debug logging is gated by `DOC_ANALYSIS_DEBUG` and hides content by default.

- `secure_analysis.py`  
  - Convenience routing for secure analysis with redaction and external APIs, with fallbacks.

- `redaction_utils.py`  
  - Redacts PII (SSN, account, routing, names, etc.), provides compliance checks.

- `replicate_utils.py`  
  - Optional Replicate-based bank statement analysis (not wired into the main flow).

- `tasks.py`  
  - Celery task to store embeddings asynchronously.

- `management/commands/ensure_pgvector.py`  
  - Checks/enables the pgvector extension in Postgres.

- `migrations/`  
  - Initial model and embedding dimension update to 1536.

## Integration with the rest of the project
- Included in `realestate/urls.py` (as `/doc_analysis/`).
- Used by application processing/Celery tasks in `applications/tasks.py` to analyze uploaded bank statements via secure LLM path.
- Broker/Superadmin UI flow: In Applications pages, brokers click “Start Analysis,” which calls `applications.views.analyze_uploaded_file` to enqueue `applications.tasks.analyze_document_async`. That task runs extraction, tamper check, secure LLM analysis, and saves JSON to `UploadedFile.analysis_results`. The UI polls `applications.views.check_analysis_status` and renders results in templates (`application_detail.html`, `v2/broker_management.html`, `v2/application_overview.html`).

## Security/permissions
- Endpoint requires login, CSRF, POST, permission `doc_analysis.can_analyze_documents`, and user-based rate limiting (env: `DOC_ANALYSIS_RATE_LIMIT`, `DOC_ANALYSIS_RATE_WINDOW`).
- External LLM calls use redaction and can be disabled by withholding API keys.
- Debug logging is gated via `DOC_ANALYSIS_DEBUG` to avoid leaking content/PII.

## Embeddings and search
- Embedding generation: triggered after extraction; runs via Celery task (`store_document_embeddings_task`), falls back to sync if Celery is down.  
- OpenAI config: `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL` (default `text-embedding-3-small`), `OPENAI_EMBEDDING_DIM` (default `1536`).  
- pgvector must be enabled; use `python manage.py ensure_pgvector` or add the provided migration.  
- Search: POST `/doc_analysis/search/` or UI at `/doc_analysis/search/ui/`.

## Tamper detection
- `detect_pdf_modifications` returns metadata comparison, per-page fingerprints (hashes, content sizes, images/XObjects), object summary, notes, `tampering_suspected`, and `severity`. The view also surfaces `tampering_suspected`/`tampering_severity` at the top level.

## How to run key commands
- Ensure pgvector: `python manage.py ensure_pgvector` (or apply migrations).  
- Analyze API: POST `/doc_analysis/analyze/` with `file` and `document_type` (`Bank Statement`, `Pay Stub`, `Tax Return`).  
- Embedding search API: POST `/doc_analysis/search/` with `query` (and optional `k`).  
- Embedding search UI: visit `/doc_analysis/search/ui/`.
