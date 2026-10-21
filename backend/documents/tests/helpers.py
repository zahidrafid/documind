import math
import re
import shutil
import tempfile
import zlib
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

EMBEDDING_DIMENSIONS = 1536


def fake_embed_texts(texts, batch_size=100):
    """Deterministic stand-in for OpenAI embeddings.

    Each word adds weight to one dimension, so texts that share words are
    close together and texts with no words in common are far apart.
    """
    vectors = []
    for text in texts:
        vector = [0.0] * EMBEDDING_DIMENSIONS
        vector[0] = 0.01  # never an all-zero vector
        for word in re.findall(r"\w+", text.lower()):
            vector[1 + zlib.crc32(word.encode()) % (EMBEDDING_DIMENSIONS - 1)] += 1.0
        norm = math.sqrt(sum(v * v for v in vector))
        vectors.append([v / norm for v in vector])
    return vectors


def make_pdf(page_texts):
    """Build a small, valid PDF with one line of text per page."""
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    kids = []
    next_id = 4
    for text in page_texts:
        page_id, content_id = next_id, next_id + 1
        next_id += 2
        kids.append(page_id)
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET".encode("latin-1")
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode()
        objects[content_id] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream"
        )
    kid_refs = " ".join(f"{kid} 0 R" for kid in kids)
    objects[2] = f"<< /Type /Pages /Kids [{kid_refs}] /Count {len(kids)} >>".encode()

    output = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for object_id in sorted(objects):
        offsets[object_id] = len(output)
        output += f"{object_id} 0 obj\n".encode() + objects[object_id] + b"\nendobj\n"

    xref_position = len(output)
    size = max(objects) + 1
    output += f"xref\n0 {size}\n0000000000 65535 f \n".encode()
    for object_id in range(1, size):
        output += f"{offsets[object_id]:010d} 00000 n \n".encode()
    output += (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{xref_position}\n%%EOF\n"
    ).encode()
    return bytes(output)


def pdf_upload(name, page_texts):
    return SimpleUploadedFile(name, make_pdf(page_texts), content_type="application/pdf")


def create_ready_document(owner, title, page_texts):
    """Create a document and run the real ingestion pipeline on it (with fake embeddings)."""
    from documents.models import Document
    from documents.services.ingestion import ingest_document

    document = Document.objects.create(
        owner=owner, title=title, file=pdf_upload(f"{title}.pdf", page_texts)
    )
    ingest_document(document)
    document.refresh_from_db()
    return document


class TempMediaMixin:
    """Save uploaded files to a temporary folder that's deleted after each test."""

    def setUp(self):
        super().setUp()
        media_root = tempfile.mkdtemp()
        override = override_settings(MEDIA_ROOT=media_root)
        override.enable()
        self.addCleanup(override.disable)
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)


class FakeOpenAIMixin:
    """Replace every OpenAI call with a fake, and fail loudly if a real one slips through."""

    chat_reply = "Late work loses ten percent per day [1]."

    def setUp(self):
        super().setUp()
        self._patch(
            "documents.services.openai_client.get_client",
            side_effect=AssertionError("Tests must not call the real OpenAI API"),
        )
        self._patch("documents.services.ingestion.embed_texts", side_effect=fake_embed_texts)
        self._patch("documents.services.qa.embed_texts", side_effect=fake_embed_texts)
        self.mock_chat = self._patch("documents.services.qa.chat", return_value=self.chat_reply)

    def _patch(self, target, **kwargs):
        patcher = mock.patch(target, **kwargs)
        mocked = patcher.start()
        self.addCleanup(patcher.stop)
        return mocked
