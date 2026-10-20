import logging
from pathlib import Path

import openai
from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Document
from .serializers import AskSerializer, DocumentSerializer
from .services.ingestion import ingest_document
from .services.qa import answer_question

logger = logging.getLogger(__name__)


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

        try:
            ingest_document(document)
        except Exception:
            # ingest_document already saved status=failed and the error message
            logger.exception("Ingestion failed for document %s", document.id)

        document.refresh_from_db()
        return Response(
            self.get_serializer(document).data, status=status.HTTP_201_CREATED
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
