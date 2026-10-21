from django.contrib.postgres.search import SearchVector
from django.db import transaction

from documents.models import Chunk, Document

from .chunking import chunk_pages
from .openai_client import embed_texts
from .pdf import extract_pages


def ingest_document(document):
    """Extract, chunk, embed and store a document. Updates its status."""
    document.status = Document.Status.PROCESSING
    document.error_message = ""
    document.save(update_fields=["status", "error_message"])

    try:
        pages, page_count = extract_pages(document.file.path)
        if not pages:
            raise ValueError(
                "No text found in this PDF. It may be a scanned image."
            )

        chunks = chunk_pages(pages)
        vectors = embed_texts([chunk.text for chunk in chunks])

        with transaction.atomic():
            document.chunks.all().delete()  # makes re-ingesting safe
            Chunk.objects.bulk_create(
                Chunk(
                    document=document,
                    page_number=chunk.page_number,
                    chunk_index=index,
                    text=chunk.text,
                    embedding=vector,
                )
                for index, (chunk, vector) in enumerate(zip(chunks, vectors))
            )
            document.chunks.update(
                search_vector=SearchVector("text", config="english")
            )
            document.page_count = page_count
            document.status = Document.Status.READY
            document.save(update_fields=["page_count", "status"])

    except Exception as exc:
        document.status = Document.Status.FAILED
        document.error_message = str(exc)
        document.save(update_fields=["status", "error_message"])
        raise

    return len(chunks)
