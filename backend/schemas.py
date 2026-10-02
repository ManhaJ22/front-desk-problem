"""Pydantic models: LLM structured outputs and API request/response shapes.

API shapes must match docs/architecture.md (API contract) and frontend/src/mockApi.js.
"""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, StringConstraints, field_validator

from backend.config import KB_CATEGORIES

# --- LLM outputs (passed to Gemini as response_schema) --------------------------------


class SensitivityCategory(str, Enum):
    health = "health"
    safety = "safety"
    allergies = "allergies"
    custody_legal = "custody_legal"
    emotional_social = "emotional_social"
    none = "none"


class SensitivityResult(BaseModel):
    category: SensitivityCategory
    score: int  # 1-5; clamped by sensitivity.py
    rationale: str
    # Urgency is judged in the same call, in context (decision log #44).
    is_urgent: bool = False
    urgency_reason: str = ""


class GeneratedAnswer(BaseModel):
    answer: str
    claimed_facts: list[str]
    # False when the excerpts only partly cover the question (decision log #42).
    fully_answers_question: bool = True


# --- API ---------------------------------------------------------------------------------

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]


class Source(BaseModel):
    id: str
    title: str


class AskResponse(BaseModel):
    log_id: int
    escalated: bool
    answer: str | None
    message: str | None
    sources: list[Source]


class ChunkIn(BaseModel):
    category: str
    title: NonEmpty
    content: NonEmpty

    @field_validator("category")
    @classmethod
    def known_category(cls, v: str) -> str:
        if v not in KB_CATEGORIES:
            raise ValueError(f"category must be one of {KB_CATEGORIES}")
        return v


class ChunkOut(BaseModel):
    id: str
    category: str
    title: str
    content: str
    source: str  # 'handbook' | 'staff' (decision log #28)
    updated_at: str


class QuestionOut(BaseModel):
    id: int
    created_at: str
    question: str
    answer: str | None
    escalated: bool
    escalation_reason: str | None
    is_sensitive: bool
    is_urgent: bool
    urgency_reason: str | None  # classifier's reason; None when the keyword fallback decided (#44)
    sensitivity_category: str | None
    sensitivity_score: int | None
    sensitivity_rationale: str | None
    semantic_score: float | None
    adherence_score: float | None
    combined_score: float | None
    threshold_used: float | None
    retrieved_chunk_ids: list[str]
    claimed_facts: list[str]
    unmatched_facts: list[str]
    answer_shown: bool  # parent saw the generated answer (decision log #37)
    resolved: bool
    priority: int


class AddToKbResponse(BaseModel):
    chunk: ChunkOut
    question: QuestionOut


class Stats(BaseModel):
    total: int
    answered: int
    escalated: int
    unresolved: int
    by_reason: dict[str, int]
