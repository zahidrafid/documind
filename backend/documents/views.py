import logging
from pathlib import Path

from django.db import transaction
from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response

from accounts.permissions import DemoReadOnly

from .models import Document
from .serializers import DocumentSerializer
from .tasks import process_document

logger = logging.getLogger(__name__)


def enqueue_processing(document):
    """Queue a document for background processing."""
    try:
        process_document.delay(document.id)
    except Exception:
        # Usually means Redis isn't running
        logger.exception("Could not queue document %s", document.id)
        Document.objects.filter(id=document.id).update(
            status=Document.Status.FAILED,
            error_message="Couldn't start processing. Please try again later.",
        )


class DocumentViewSet(viewsets.ModelViewSet):
    serializer_class = DocumentSerializer
    http_method_names = ["get", "post", "delete", "head", "options"]
    permission_classes = [IsAuthenticated, DemoReadOnly]

    def get_throttles(self):
        if self.action == "create":
            self.throttle_scope = "upload"
            return [ScopedRateThrottle()]
        return super().get_throttles()

    def get_queryset(self):
        # Users only ever see their own documents
        return Document.objects.filter(owner=self.request.user).annotate(
            chunk_count=Count("chunks")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded = serializer.validated_data["file"]
        title = serializer.validated_data.get("title") or Path(uploaded.name).stem
        document = serializer.save(owner=request.user, title=title[:255])

        # Queue the job only once the document is definitely saved,
        # so the worker never looks for a row that doesn't exist yet
        transaction.on_commit(lambda: enqueue_processing(document))

        document.refresh_from_db()
        return Response(
            self.get_serializer(document).data, status=status.HTTP_202_ACCEPTED
        )

    @action(detail=True, methods=["post"])
    def reprocess(self, request, pk=None):
        document = self.get_object()  # still only finds the user's own documents
        if document.status in (Document.Status.PENDING, Document.Status.PROCESSING):
            return Response(
                {"detail": "This document is already being processed."},
                status=status.HTTP_409_CONFLICT,
            )

        document.status = Document.Status.PENDING
        document.error_message = ""
        document.save(update_fields=["status", "error_message"])
        transaction.on_commit(lambda: enqueue_processing(document))

        document.refresh_from_db()
        return Response(
            self.get_serializer(document).data, status=status.HTTP_202_ACCEPTED
        )

    def perform_destroy(self, instance):
        instance.file.delete(save=False)  # remove the PDF from disk too
        instance.delete()  # chunks are deleted automatically (CASCADE)

