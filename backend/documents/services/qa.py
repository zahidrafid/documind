import re

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
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

CANDIDATES_PER_METHOD = 20  # how many results each search method contributes
RRF_K = 60  # standard Reciprocal Rank Fusion constant
SEARCH_MODES = ("vector", "keyword", "hybrid")


def _user_chunks(user, document_ids):
    """Chunks the user is allowed to search."""
    chunks = Chunk.objects.filter(
        document__owner=user,
        document__status=Document.Status.READY,
    )
    if document_ids:
        chunks = chunks.filter(document_id__in=document_ids)
    return chunks.select_related("document")


def _keyword_query(question):
    """Match chunks containing ANY of the question's words.

    Requiring ALL words would be too strict for natural questions.
    Chunks matching more words still rank higher.
    Common words like "what" and "the" are ignored automatically.
    """
    words = re.findall(r"\w+", question.lower())[:30]
    query = None
    for word in words:
        term = SearchQuery(word, search_type="plain", config="english")
        query = term if query is None else query | term
    return query


def _vector_search(chunks, question_vector, limit):
    return list(
        chunks.annotate(distance=CosineDistance("embedding", question_vector))
        .order_by("distance")[:limit]
    )


def _keyword_search(chunks, question, question_vector, limit):
    query = _keyword_query(question)
    if query is None:
        return []
    return list(
        chunks.filter(search_vector=query)
        .annotate(
            rank=SearchRank("search_vector", query),
            distance=CosineDistance("embedding", question_vector),
        )
        .order_by("-rank")[:limit]
    )


def search_chunks(question, user, top_k=5, document_ids=None, mode=None):
    """Return the best chunks for a question, best first.

    Each chunk gets extra attributes:
      distance  cosine distance to the question (lower = more similar)
      match     "vector", "keyword" or "both"
      score     fused ranking score
    """
    mode = mode or settings.SEARCH_MODE
    if mode not in SEARCH_MODES:
        raise ValueError(f"Unknown search mode: {mode}")

    chunks = _user_chunks(user, document_ids)
    question_vector = embed_texts([question])[0]

    result_lists = {}
    if mode in ("vector", "hybrid"):
        result_lists["vector"] = _vector_search(chunks, question_vector, CANDIDATES_PER_METHOD)
    if mode in ("keyword", "hybrid"):
        result_lists["keyword"] = _keyword_search(
            chunks, question, question_vector, CANDIDATES_PER_METHOD
        )

    # Reciprocal Rank Fusion: score = sum of 1 / (k + position) across lists
    scores, found_by, by_id = {}, {}, {}
    for method, results in result_lists.items():
        for position, chunk in enumerate(results, start=1):
            scores[chunk.id] = scores.get(chunk.id, 0) + 1 / (RRF_K + position)
            found_by.setdefault(chunk.id, set()).add(method)
            by_id.setdefault(chunk.id, chunk)

    best_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]

    results = []
    for chunk_id in best_ids:
        chunk = by_id[chunk_id]
        methods = found_by[chunk_id]
        chunk.match = "both" if len(methods) == 2 else next(iter(methods))
        chunk.score = scores[chunk_id]
        results.append(chunk)
    return results


def answer_question(
    question, user, top_k=5, max_distance=0.65, document_ids=None, mode=None
):
    chunks = search_chunks(
        question, user, top_k=top_k, document_ids=document_ids, mode=mode
    )

    # Keep chunks that are close in meaning OR contain the question's words.
    # A chunk with an exact course code may not be close in meaning, but it's relevant.
    relevant = [
        chunk
        for chunk in chunks
        if chunk.distance <= max_distance or chunk.match in ("keyword", "both")
    ]
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
            "match": chunk.match,
        }
        for number, chunk in enumerate(relevant, start=1)
    ]
    return {"answer": answer, "sources": sources}
