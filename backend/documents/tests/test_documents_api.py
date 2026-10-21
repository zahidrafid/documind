from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from documents.models import Chunk, Document

from .helpers import FakeOpenAIMixin, TempMediaMixin, create_ready_document, make_pdf, pdf_upload

User = get_user_model()


class DocumentApiTests(TempMediaMixin, FakeOpenAIMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.alice = User.objects.create_user("alice", password="test-pass-12345")
        self.bob = User.objects.create_user("bob", password="test-pass-12345")
        self.client = APIClient()
        self.client.force_authenticate(self.alice)
        self.mock_delay = self._patch("documents.views.process_document.delay")

    def upload(self, file):
        return self.client.post("/api/documents/", {"file": file}, format="multipart")

    def test_requires_authentication(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/documents/").status_code, 401)

    def test_valid_upload_is_saved_and_queued(self):
        with self.captureOnCommitCallbacks(execute=True):
            response = self.upload(pdf_upload("syllabus.pdf", ["Late work loses ten percent."]))

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["title"], "syllabus")
        self.assertNotIn("file", response.data)  # never expose a file link
        self.mock_delay.assert_called_once_with(response.data["id"])

    def test_rejects_file_that_is_not_really_a_pdf(self):
        response = self.upload(SimpleUploadedFile("fake.pdf", b"hello", content_type="application/pdf"))
        self.assertEqual(response.status_code, 400)
        self.assertIn("file", response.data)
        self.assertEqual(Document.objects.count(), 0)
        self.mock_delay.assert_not_called()

    def test_rejects_wrong_extension(self):
        response = self.upload(SimpleUploadedFile("notes.txt", make_pdf(["hi"]), content_type="text/plain"))
        self.assertEqual(response.status_code, 400)

    @override_settings(MAX_UPLOAD_SIZE_MB=0)
    def test_rejects_files_over_the_size_limit(self):
        response = self.upload(pdf_upload("big.pdf", ["Some text."]))
        self.assertEqual(response.status_code, 400)

    def test_list_shows_only_own_documents(self):
        create_ready_document(self.alice, "Mine", ["Alpha content."])
        create_ready_document(self.bob, "Bobs", ["Beta content."])

        response = self.client.get("/api/documents/")
        self.assertEqual([doc["title"] for doc in response.data], ["Mine"])
        self.assertEqual(response.data[0]["chunk_count"], 1)

    def test_cannot_view_or_delete_someone_elses_document(self):
        bobs = create_ready_document(self.bob, "Bobs", ["Beta content."])

        self.assertEqual(self.client.get(f"/api/documents/{bobs.id}/").status_code, 404)
        self.assertEqual(self.client.delete(f"/api/documents/{bobs.id}/").status_code, 404)
        self.assertTrue(Document.objects.filter(id=bobs.id).exists())

    def test_delete_removes_file_and_chunks(self):
        document = create_ready_document(self.alice, "Mine", ["Alpha content."])
        file_path = Path(document.file.path)
        self.assertTrue(file_path.exists())

        response = self.client.delete(f"/api/documents/{document.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(file_path.exists())
        self.assertFalse(Chunk.objects.filter(document_id=document.id).exists())

    def test_reprocess_is_rejected_while_processing(self):
        document = Document.objects.create(
            owner=self.alice, title="Busy", file=pdf_upload("busy.pdf", ["Text."]),
            status=Document.Status.PROCESSING,
        )
        response = self.client.post(f"/api/documents/{document.id}/reprocess/")
        self.assertEqual(response.status_code, 409)

    def test_reprocess_queues_a_failed_document(self):
        document = Document.objects.create(
            owner=self.alice, title="Broken", file=pdf_upload("broken.pdf", ["Text."]),
            status=Document.Status.FAILED, error_message="Something went wrong",
        )
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(f"/api/documents/{document.id}/reprocess/")

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.data["status"], "pending")
        self.assertEqual(response.data["error_message"], "")
        self.mock_delay.assert_called_once_with(document.id)

    @override_settings(MAX_DOCUMENTS_PER_USER=1)
    def test_document_limit_per_user(self):
        create_ready_document(self.alice, "First", ["Alpha content."])
        response = self.upload(pdf_upload("second.pdf", ["Beta content."]))
        self.assertEqual(response.status_code, 400)
        self.assertIn("up to 1 documents", str(response.data))
