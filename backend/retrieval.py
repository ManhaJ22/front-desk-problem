"""Embed the question, rank handbook chunks by cosine similarity, score retrieval quality."""

import math
from dataclasses import dataclass

from backend import config, db, gemini


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    title: str
    content: str
    cosine: float
    source: str = "handbook"  # 'staff' if written/edited in the dashboard (decision log #28)


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


def retrieve(question: str) -> list[RetrievedChunk]:
    """Top TOP_K chunks by cosine similarity, best first. Empty list if the KB is empty."""
    query = gemini.embed([question], "RETRIEVAL_QUERY")[0]
    scored = [
        RetrievedChunk(c["id"], c["title"], c["content"], cosine(query, c["embedding"]), c["source"])
        for c in db.list_chunks(with_embedding=True)
    ]
    scored.sort(key=lambda c: c.cosine, reverse=True)
    return scored[: config.TOP_K]


def is_out_of_scope(hits: list[RetrievedChunk]) -> bool:
    return not hits or hits[0].cosine < config.SIMILARITY_FLOOR


def relevant(hits: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Hits that clear the floor: what generation sees AND what adherence checks against."""
    return [h for h in hits if h.cosine >= config.SIMILARITY_FLOOR]


def semantic_score(top_cosine: float) -> float:
    """Map raw cosine onto 0-1: 0 at SEMANTIC_ZERO, 1 at SIMILARITY_CEILING.

    Deliberately NOT anchored at SIMILARITY_FLOOR: the floor is a yes/no relevance gate, and
    anchoring the scale there made in-scope questions just above it unanswerable even with
    every fact verified (decision log #21).
    """
    span = config.SIMILARITY_CEILING - config.SEMANTIC_ZERO
    return max(0.0, min(1.0, (top_cosine - config.SEMANTIC_ZERO) / span))
