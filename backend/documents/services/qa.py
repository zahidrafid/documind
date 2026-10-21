import re

from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank
from pgvector.django import CosineDistance

from documents.models import Chunk, Document

from .openai_client import chat, chat_json, embed_texts

SYSTEM_PROMPT = """You are DocuMind, an assistant that answers questions using ONLY the numbered sources provided.

Rules:
- Base every statement on the sources. Do not use outside knowledge.
- Cite the source number in square brackets after each claim, like [1] or [2][3].
- If the sources do not contain the answer, reply exactly: "I couldn't find that in your documents."
- Be concise and clear.
- The conversation so far is only there to help you understand the question. Facts must still come from the sources."""

NOT_FOUND_MESSAGE = "I couldn't find that in your documents."

REWRITE_PROMPT = """You rewrite follow-up questions so they can be understood without the conversation.

Only add context when the question depends on the conversation, for example when it uses words like "it", "that", "this", "they", "those", "too" or "also", or starts with "what about". If the question already makes sense on its own, return it exactly as written.

Examples:
Conversation about the late work policy. Question: "Does that apply to the final project too?"
Rewritten: "Does the late work policy apply to the final project?"

Conversation about the late work policy. Question: "Who is the instructor?"
Rewritten: "Who is the instructor?"

Conversation about the AI use policy. Question: "How many credit hours is this course?"
Rewritten: "How many credit hours is this course?"

Do not answer the question. Return only the question, nothing else."""

EXPAND_PROMPT = """You help a search engine find passages in a user's documents.

Given the conversation (if any) and the user's latest question, return JSON in this shape:
{"standalone": "...", "alternatives": ["...", "..."]}

- "standalone": the question rewritten so it makes sense without the conversation. Only add context if the question refers to something earlier (words like "it", "that", "this", "they", "too", "also", or "what about"). Otherwise copy it exactly.
- "alternatives": two short rephrasings that use different words a document might use instead: synonyms, formal terms, or form labels. For example, "instructor" might appear in a document as "professor" or "faculty name", and "late work" as "late submissions".

Return only the JSON."""

RRF_K = 60
SEARCH_MODES = ("vector", "keyword", "hybrid")
QUERY_STRATEGIES = ("none", "rewrite", "both", "expand")

# Keeps emails, course codes and room numbers whole:
# "jlewis@collin.edu", "ITSE-1359", "111A"
TOKEN_PATTERN = re.compile(r"[\w.@+-]*\w")


# ---------- Query building ----------

def format_history(history, max_chars=600):
    lines = []
    for message in history:
        speaker = "User" if message["role"] == "user" else "Assistant"
        text = message["content"]
        if len(text) > max_chars:
            text = text[:max_chars] + "…"
        lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


def rewrite_question(question, history):
    if not history:
        return question
    user_message = (
        f"Conversation so far:\n{format_history(history)}\n\n"
        f"Follow-up question: {question}"
    )
    rewritten = chat(REWRITE_PROMPT, user_message).strip().strip('"')
    return rewritten or question


def expand_question(question, history):
    history_text = f"Conversation so far:\n{format_history(history)}\n\n" if history else ""
    data = chat_json(EXPAND_PROMPT, f"{history_text}Latest question: {question}")
    standalone = str(data.get("standalone") or question).strip()
    alternatives = [
        str(item).strip() for item in data.get("alternatives", []) if str(item).strip()
    ][:3]
    return standalone, alternatives


def _unique(queries):
    seen, result = set(), []
    for query in queries:
        key = query.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(query.strip())
    return result


def build_queries(question, history, strategy=None):
    """Return (queries, search_query).

    queries       every phrasing to search with
    search_query  the main standalone question (shown as "Searched for" in the UI)
    """
    strategy = strategy or settings.QUERY_STRATEGY
    if strategy not in QUERY_STRATEGIES:
        raise ValueError(f"Unknown query strategy: {strategy}")

    if strategy == "none":
        return [question], question

    if strategy == "expand":
        standalone, alternatives = expand_question(question, history)
        return _unique([question, standalone, *alternatives]), standalone

    standalone = rewrite_question(question, history)
    if strategy == "rewrite":
        return [standalone], standalone
    return _unique([question, standalone]), standalone  # "both"


# ---------- Search ----------

def _user_chunks(user, document_ids):
    chunks = Chunk.objects.filter(
        document__owner=user,
        document__status=Document.Status.READY,
    )
    if document_ids:
        chunks = chunks.filter(document_id__in=document_ids)
    return chunks.select_related("document")


def _keyword_query(question):
    """OR together the question's terms. Common words are ignored by Postgres."""
    tokens = TOKEN_PATTERN.findall(question.lower())[:30]
    query = None
    for token in tokens:
        term = SearchQuery(token, search_type="plain", config="english")
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


def _methods(match):
    return {"vector", "keyword"} if match == "both" else {match}


def _finalize(scores, found_by, by_id, top_k):
    best_ids = sorted(scores, key=scores.get, reverse=True)[:top_k]
    results = []
    for chunk_id in best_ids:
        chunk = by_id[chunk_id]
        methods = found_by[chunk_id]
        chunk.match = "both" if len(methods) == 2 else next(iter(methods))
        chunk.score = scores[chunk_id]
        results.append(chunk)
    return results


def search_chunks(
    question,
    user,
    top_k=5,
    document_ids=None,
    mode=None,
    question_vector=None,
    candidates=None,
    keyword_weight=None,
):
    """Search with one phrasing. Returns chunks with .distance, .match and .score."""
    mode = mode or settings.SEARCH_MODE
    if mode not in SEARCH_MODES:
        raise ValueError(f"Unknown search mode: {mode}")
    candidates = candidates or settings.SEARCH_CANDIDATES
    keyword_weight = settings.KEYWORD_WEIGHT if keyword_weight is None else keyword_weight

    chunks = _user_chunks(user, document_ids)
    if question_vector is None:
        question_vector = embed_texts([question])[0]

    result_lists = {}
    if mode in ("vector", "hybrid"):
        result_lists["vector"] = _vector_search(chunks, question_vector, candidates)
    if mode in ("keyword", "hybrid"):
        result_lists["keyword"] = _keyword_search(chunks, question, question_vector, candidates)

    # Weighted Reciprocal Rank Fusion
    weights = {"vector": 1.0, "keyword": keyword_weight}
    scores, found_by, by_id = {}, {}, {}
    for method, results in result_lists.items():
        for position, chunk in enumerate(results, start=1):
            scores[chunk.id] = scores.get(chunk.id, 0) + weights[method] / (RRF_K + position)
            found_by.setdefault(chunk.id, set()).add(method)
            by_id.setdefault(chunk.id, chunk)

    return _finalize(scores, found_by, by_id, top_k)


def retrieve(
    queries,
    user,
    top_k=5,
    document_ids=None,
    mode=None,
    candidates=None,
    keyword_weight=None,
    vectors=None,
):
    """Search with one or more phrasings and fuse the results."""
    if vectors is None:
        vectors = embed_texts(queries)  # one API call for all phrasings
    options = {
        "document_ids": document_ids,
        "mode": mode,
        "candidates": candidates,
        "keyword_weight": keyword_weight,
    }

    if len(queries) == 1:
        return search_chunks(queries[0], user, top_k=top_k, question_vector=vectors[0], **options)

    pool = candidates or settings.SEARCH_CANDIDATES
    scores, found_by, by_id = {}, {}, {}
    for query, vector in zip(queries, vectors):
        results = search_chunks(query, user, top_k=pool, question_vector=vector, **options)
        for position, chunk in enumerate(results, start=1):
            scores[chunk.id] = scores.get(chunk.id, 0) + 1 / (RRF_K + position)
            found_by.setdefault(chunk.id, set()).update(_methods(chunk.match))
            # Keep the copy with the best (smallest) distance across phrasings
            current = by_id.get(chunk.id)
            if current is None or chunk.distance < current.distance:
                by_id[chunk.id] = chunk

    return _finalize(scores, found_by, by_id, top_k)


def is_relevant(chunk, max_distance=None, keyword_max_distance=None):
    max_distance = settings.MAX_DISTANCE if max_distance is None else max_distance
    keyword_max_distance = (
        settings.KEYWORD_MAX_DISTANCE if keyword_max_distance is None else keyword_max_distance
    )
    if chunk.distance <= max_distance:
        return True
    return chunk.match in ("keyword", "both") and chunk.distance <= keyword_max_distance


# ---------- Answering ----------

def answer_question(
    question,
    user,
    history=None,
    top_k=5,
    document_ids=None,
    mode=None,
    strategy=None,
    candidates=None,
    keyword_weight=None,
    max_distance=None,
    keyword_max_distance=None,
):
    history = history or []
    queries, search_query = build_queries(question, history, strategy)

    chunks = retrieve(
        queries,
        user,
        top_k=top_k,
        document_ids=document_ids,
        mode=mode,
        candidates=candidates,
        keyword_weight=keyword_weight,
    )
    relevant = [
        chunk for chunk in chunks if is_relevant(chunk, max_distance, keyword_max_distance)
    ]
    if not relevant:
        return {
            "answer": NOT_FOUND_MESSAGE,
            "sources": [],
            "search_query": search_query,
            "queries": queries,
        }

    context = "\n\n".join(
        f"[{number}] {chunk.document.title}, page {chunk.page_number}:\n{chunk.text}"
        for number, chunk in enumerate(relevant, start=1)
    )
    history_text = f"Conversation so far:\n{format_history(history)}\n\n" if history else ""
    question_text = (
        question if search_query == question else f"{question}\n(Interpreted as: {search_query})"
    )
    user_message = f"{history_text}Sources:\n{context}\n\nQuestion: {question_text}"
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
    return {
        "answer": answer,
        "sources": sources,
        "search_query": search_query,
        "queries": queries,
    }
