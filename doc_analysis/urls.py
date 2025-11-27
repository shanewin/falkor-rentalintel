from django.urls import path
from .views import analyze_document, search_embeddings, search_embeddings_ui

urlpatterns = [
    path('analyze/', analyze_document, name='analyze_document'),
    path('search/', search_embeddings, name='search_embeddings'),
    path('search/ui/', search_embeddings_ui, name='search_embeddings_ui'),
]
