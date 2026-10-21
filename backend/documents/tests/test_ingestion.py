from django.contrib.auth import get_user_model
from django.test import TestCase

from documents.models import Document
from documents.tasks import process_document

from .helpers import FakeOpenAIMixin, TempMediaMixin, pdf_upload

User = get_user_model()


class IngestionTests(TempMediaMixin, FakeOpenAIMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user("alice", password="test-pass-12345")

    def make_document(self, page_texts):
        return Document.objects.create(
            owner=self.user, title="Doc", file=pdf_upload("doc.pdf", page_texts)
        )

    def test_processing_creates_chunks_with_pages_and_search_data(self):
        document = self.make_document(["Grading is based on quizzes.", "Attendance is required."])

        process_document(document.id)

        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.READY)
        self.assertEqual(document.page_count, 2)
        chunks = list(document.chunks.order_by("chunk_index"))
        self.assertEqual([chunk.page_number for chunk in chunks], [1, 2])
        self.assertTrue(all(chunk.search_vector for chunk in chunks))
        embedding = chunks[0].embedding
        if hasattr(embedding, "to_list"):  # pgvector may return a Vector object
            embedding = embedding.to_list()
        self.assertEqual(len(embedding), 1536)

    def test_running_twice_does_not_duplicate_chunks(self):
        document = self.make_document(["Grading is based on quizzes.", "Attendance is required."])

        process_document(document.id)
        process_document(document.id)  # e.g. a job redelivered after a worker crash

        self.assertEqual(document.chunks.count(), 2)

    def test_pdf_without_text_is_marked_failed(self):
        document = self.make_document([""])

        with self.assertRaises(ValueError):
            process_document(document.id)

        document.refresh_from_db()
        self.assertEqual(document.status, Document.Status.FAILED)
        self.assertIn("No text found", document.error_message)
        self.assertEqual(document.chunks.count(), 0)

    def test_deleted_document_is_skipped(self):
        document = self.make_document(["Some text."])
        document_id = document.id
        document.delete()

        self.assertIsNone(process_document(document_id))
