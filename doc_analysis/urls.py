from django.urls import path
from .views import analyze_document

urlpatterns = [
    path('analyze/', analyze_document, name='analyze_document'),
]