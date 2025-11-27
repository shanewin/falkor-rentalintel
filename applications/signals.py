from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import UploadedFile, RequiredDocumentType
from .tasks import analyze_document_async

@receiver(post_save, sender=UploadedFile)
def auto_analyze_document(sender, instance, created, **kwargs):
    """
    Automatically trigger document analysis when a file is uploaded.
    Only triggers for analyzable document types.
    """
    if created and instance.document_type:
        # Define analyzable types
        analyzable_types = [
            RequiredDocumentType.PAYSTUB,
            RequiredDocumentType.BANK_STATEMENT,
            RequiredDocumentType.TAX_FORM,
            # Legacy types
            RequiredDocumentType.PAY_STUB,
            RequiredDocumentType.TAX_RETURN,
        ]
        
        if instance.document_type in analyzable_types:
            # Trigger Celery task
            task = analyze_document_async.delay(instance.id)
            
            # Save task ID
            instance.celery_task_id = task.id
            instance.save(update_fields=['celery_task_id'])
