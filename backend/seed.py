"""Seed handbook_chunks from data/handbook.json when the table is empty.

Runs at every startup. On Render's free tier the disk is ephemeral, so this
re-seeds on every cold boot (decision log #11).
"""

import json

from backend import config, db, gemini
from backend.kb import embedding_text


def seed_if_empty() -> int:
    """Returns the number of chunks inserted (0 if the table already had data)."""
    if db.count_chunks():
        return 0
    with open(config.HANDBOOK_PATH, encoding="utf-8") as f:
        chunks = json.load(f)
    vectors = gemini.embed(
        [embedding_text(c["title"], c["content"]) for c in chunks],
        "RETRIEVAL_DOCUMENT",
    )
    for c, vector in zip(chunks, vectors, strict=True):
        db.upsert_chunk(c["id"], c["category"], c["title"], c["content"], vector, source="handbook")
    return len(chunks)
