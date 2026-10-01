"""Knowledge-base edits. Every write re-embeds the chunk so retrieval stays in sync."""

import re

from backend import db, gemini


def embedding_text(title: str, content: str) -> str:
    """The exact text embedded for a chunk (seed and edits must agree)."""
    return f"{title}\n\n{content}"


def _embed(title: str, content: str) -> list[float]:
    return gemini.embed([embedding_text(title, content)], "RETRIEVAL_DOCUMENT")[0]


def slugify(title: str) -> str:
    """URL-safe id from a title, suffixed -2, -3, ... if already taken."""
    base = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60].strip("-") or "chunk"
    chunk_id, n = base, 2
    while db.chunk_exists(chunk_id):
        chunk_id, n = f"{base}-{n}", n + 1
    return chunk_id


def create_chunk(category: str, title: str, content: str) -> dict:
    return db.upsert_chunk(slugify(title), category, title, content, _embed(title, content))


def update_chunk(chunk_id: str, category: str, title: str, content: str) -> dict | None:
    """Returns None if the chunk doesn't exist."""
    if not db.chunk_exists(chunk_id):
        return None
    return db.upsert_chunk(chunk_id, category, title, content, _embed(title, content))


def delete_chunk(chunk_id: str) -> bool:
    return db.delete_chunk(chunk_id)
