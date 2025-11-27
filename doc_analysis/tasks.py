from celery import shared_task
from .utils import store_document_embeddings


@shared_task
def store_document_embeddings_task(file_name: str, text_chunks, max_chunks: int = 20):
    """
    Async wrapper to store embeddings without blocking the request thread.
    """
    return store_document_embeddings(file_name, text_chunks, max_chunks=max_chunks)
