from django.conf import settings
from rest_framework import serializers

from .models import Document


class DocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)
    title = serializers.CharField(max_length=255, required=False, allow_blank=True)
    chunk_count = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "title",
            "file",
            "status",
            "error_message",
            "page_count",
            "chunk_count",
            "uploaded_at",
        ]
        read_only_fields = ["status", "error_message", "page_count", "uploaded_at"]

    def get_chunk_count(self, obj):
        # Uses the annotated value from the list query when it's there
        count = getattr(obj, "chunk_count", None)
        return count if count is not None else obj.chunks.count()

    def validate_file(self, uploaded):
        if not uploaded.name.lower().endswith(".pdf"):
            raise serializers.ValidationError("Only PDF files are supported.")

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if uploaded.size > max_bytes:
            raise serializers.ValidationError(
                f"File is too large. The limit is {settings.MAX_UPLOAD_SIZE_MB} MB."
            )

        # Check the file's first bytes, not just its name: real PDFs start with %PDF-
        header = uploaded.read(5)
        uploaded.seek(0)
        if header != b"%PDF-":
            raise serializers.ValidationError("This file doesn't look like a valid PDF.")

        return uploaded

