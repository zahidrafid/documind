import logging
from pathlib import Path

import openai
from django.db import transaction
from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Document
from .serializers import AskSerializer, DocumentSerializer
from .services.qa import answer_question
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


class AskView(APIView):
    def post(self, request):
        serializer = AskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            result = answer_question(
                data["question"],
                request.user,
                top_k=data["top_k"],
                document_ids=data.get("document_ids"),
            )
        except openai.OpenAIError:
            logger.exception("OpenAI request failed")
            return Response(
                {"detail": "The AI service is unavailable right now. Please try again."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(result)
