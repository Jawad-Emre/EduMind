from datetime import datetime
from pydantic import BaseModel, Field


class QuizGenerateRequest(BaseModel):
    subject_id: int
    material_id: int | None = None
    session_id: int | None = None
    # Clamp to a sane range: at least 1 question, at most 20 (keeps the LLM
    # prompt/response size bounded and generation reliable).
    num_questions: int = Field(default=5, ge=1, le=20)


class QuizSubmitRequest(BaseModel):
    answers: list[str]


class QuizResponse(BaseModel):
    id: int
    user_id: int
    subject_id: int
    questions: list[dict]
    score: float | None
    created_at: datetime

    class Config:
        from_attributes = True