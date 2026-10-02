"""Parent-facing endpoint."""

from fastapi import APIRouter

from backend import pipeline
from backend.schemas import AskRequest, AskResponse

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    return pipeline.answer_question(req.question, [turn.model_dump() for turn in req.history])
