import logging

import openai
from celery import shared_task

from .models import Document
from .services.ingestion import ingest_document

logger = logging.getLogger(__name__)

# Temporary problems that are worth retrying. Things like a bad API key
# or a scanned PDF will fail the same way every time, so they aren't retried.
RETRYABLE_ERRORS = (
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.APITimeoutError,
    openai.InternalServerError,
)


@shared_task(bind=True, max_retries=3)
def process_document(self, document_id):
    try:
        document = Document.objects.get(id=document_id)
    except Document.DoesNotExist:
        logger.info("Document %s was deleted before processing", document_id)
        return

    try:
        return ingest_document(document)
    except RETRYABLE_ERRORS as exc:
        if self.request.retries < self.max_retries:
            wait_seconds = 10 * 2 ** self.request.retries  # 10s, 20s, 40s
            Document.objects.filter(id=document_id).update(
                status=Document.Status.PENDING,
                error_message="Temporary problem reaching the AI service. Retrying…",
            )
            raise self.retry(exc=exc, countdown=wait_seconds)
        raise
