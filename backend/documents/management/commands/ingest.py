from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from documents.models import Document
from documents.services.ingestion import ingest_document


class Command(BaseCommand):
    help = "Upload a PDF for a user and process it into searchable chunks."

    def add_arguments(self, parser):
        parser.add_argument("pdf_path", help="Path to the PDF file")
        parser.add_argument("--user", required=True, help="Username of the owner")
        parser.add_argument("--title", help="Title (defaults to the file name)")

    def handle(self, *args, **options):
        path = Path(options["pdf_path"])
        if not path.exists() or path.suffix.lower() != ".pdf":
            raise CommandError(f"Not a PDF file: {path}")

        User = get_user_model()
        try:
            user = User.objects.get(username=options["user"])
        except User.DoesNotExist:
            raise CommandError(f"No user named {options['user']!r}")

        document = Document(owner=user, title=options["title"] or path.stem)
        with path.open("rb") as f:
            document.file.save(path.name, File(f), save=True)

        self.stdout.write(f"Processing {document.title!r}...")
        try:
            chunk_count = ingest_document(document)
        except Exception as exc:
            raise CommandError(f"Failed: {exc}")

        self.stdout.write(self.style.SUCCESS(
            f"Done: {document.page_count} pages, {chunk_count} chunks (document id {document.id})"
        ))
