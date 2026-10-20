import os
from functools import lru_cache

from openai import OpenAI


@lru_cache(maxsize=1)
def get_client():
    # Reads OPENAI_API_KEY from the environment (loaded from .env in settings.py)
    return OpenAI()


def embedding_model():
    return os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def chat_model():
    return os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")


def embed_texts(texts, batch_size=100):
    """Return one embedding vector per input text, in the same order."""
    vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        response = get_client().embeddings.create(model=embedding_model(), input=batch)
        vectors.extend(item.embedding for item in response.data)
    return vectors


def chat(system_prompt, user_message):
    response = get_client().chat.completions.create(
        model=chat_model(),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    )
    return response.choices[0].message.content
