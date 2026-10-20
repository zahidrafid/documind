from pgvector.django import CosineDistance

from documents.models import Chunk, Document

from .openai_client import chat, embed_texts

SYSTEM_PROMPT = """You are DocuMind, an assistant that answers questions using ONLY the numbered sources provided.

Rules:
- Base every statement on the sources. Do not use outside knowledge.
- Cite the source number in square brackets after each claim, like [1] or [2][3].
- If the sources do not contain the answer, reply exactly: "I couldn't find that in your documents."
- Be concise and clear."""

NOT_FOUND_MESSAGE = "I couldn't find that in your documents."


def search_chunks(question, user, top_k=5, document_ids=None):
    """Return the user's chunks most similar to the question, closest first."""
    question_vector = embed_texts([question])[0]

    chunks = Chunk.objects.filter(
        document__owner=user,
        document__status=Document.Status.READY,
    )
    if document_ids:
        chunks = chunks.filter(document_id__in=document_ids)

    return list(
        chunks.select_related("document")
        .annotate(distance=CosineDistance("embedding", question_vector))
        .order_by("distance")[:top_k]
    )


def answer_question(question, user, top_k=5, max_distance=0.65, document_ids=None):
    chunks = search_chunks(question, user, top_k=top_k, document_ids=document_ids)

    # Drop chunks that aren't actually similar to the question
    relevant = [chunk for chunk in chunks if chunk.distance <= max_distance]
    if not relevant:
        return {"answer": NOT_FOUND_MESSAGE, "sources": []}

    context = "\n\n".join(
        f"[{number}] {chunk.document.title}, page {chunk.page_number}:\n{chunk.text}"
        for number, chunk in enumerate(relevant, start=1)
    )
    user_message = f"Sources:\n{context}\n\nQuestion: {question}"
    answer = chat(SYSTEM_PROMPT, user_message)

    sources = [
        {
            "number": number,
            "document_id": chunk.document_id,
            "title": chunk.document.title,
            "page": chunk.page_number,
            "text": chunk.text,
            "distance": round(float(chunk.distance), 3),
        }
        for number, chunk in enumerate(relevant, start=1)
    ]
    return {"answer": answer, "sources": sources}
