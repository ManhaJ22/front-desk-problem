"""Operator endpoints: question review and knowledge-base editing (kept as separate sections)."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Response

from backend import db, kb
from backend.schemas import AddToKbResponse, ChunkIn, ChunkOut, QuestionOut, Stats
from backend.triage import priority, sort_queue

router = APIRouter(prefix="/operator")

ESCALATION_REASONS = ("out_of_scope", "sensitive_forced", "below_threshold", "partial_answer", "system_error")


def _with_priority(row: dict) -> dict:
    return {**row, "priority": priority(row["is_sensitive"], row["is_urgent"])}


def _question_or_404(question_id: int) -> dict:
    row = db.get_log(question_id)
    if row is None:
        raise HTTPException(404, "Question not found")
    return row


# --- Question review -----------------------------------------------------------------------


@router.get("/questions", response_model=list[QuestionOut])
def list_questions(view: Literal["needs_review", "all"] = "needs_review") -> list[dict]:
    return sort_queue([_with_priority(r) for r in db.list_logs(view)])


@router.post("/questions/{question_id}/resolve", response_model=QuestionOut)
def resolve_question(question_id: int) -> dict:
    _question_or_404(question_id)
    return _with_priority(db.mark_resolved(question_id))


@router.post("/questions/{question_id}/add-to-kb", response_model=AddToKbResponse)
def add_to_kb(question_id: int, body: ChunkIn) -> dict:
    """Create a NEW chunk from the operator's answer, then resolve the question (architecture item M)."""
    _question_or_404(question_id)
    chunk = kb.create_chunk(body.category, body.title, body.content)
    question = _with_priority(db.mark_resolved(question_id))
    return {"chunk": chunk, "question": question}


@router.get("/stats", response_model=Stats)
def stats() -> dict:
    rows = db.list_logs("all")
    escalated = [r for r in rows if r["escalated"]]
    return {
        "total": len(rows),
        "answered": len(rows) - len(escalated),
        "escalated": len(escalated),
        "unresolved": sum(1 for r in escalated if not r["resolved"]),
        "by_reason": {reason: sum(1 for r in escalated if r["escalation_reason"] == reason) for reason in ESCALATION_REASONS},
    }


# --- Knowledge base -------------------------------------------------------------------------


@router.get("/kb", response_model=list[ChunkOut])
def list_kb() -> list[dict]:
    return db.list_chunks()


@router.post("/kb", response_model=ChunkOut, status_code=201)
def create_kb_chunk(body: ChunkIn) -> dict:
    return kb.create_chunk(body.category, body.title, body.content)


@router.put("/kb/{chunk_id}", response_model=ChunkOut)
def update_kb_chunk(chunk_id: str, body: ChunkIn) -> dict:
    chunk = kb.update_chunk(chunk_id, body.category, body.title, body.content)
    if chunk is None:
        raise HTTPException(404, "Chunk not found")
    return chunk


@router.delete("/kb/{chunk_id}", status_code=204)
def delete_kb_chunk(chunk_id: str) -> Response:
    if not kb.delete_chunk(chunk_id):
        raise HTTPException(404, "Chunk not found")
    return Response(status_code=204)
