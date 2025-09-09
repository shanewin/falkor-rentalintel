from django.db import models
from pgvector.django import VectorField

class DocumentEmbedding(models.Model):
    file_name = models.CharField(max_length=255)
    content = models.TextField()
    embedding = VectorField(dimensions=768)