from datetime import datetime
from pydantic import BaseModel, Field


class QuizGenerateRequest(BaseModel):
    subject_id: int
    material_id: int | None = None
    session_id: int | None = None
    # Keep quiz generation reliable by limiting it to 5 or 10 questions.
    num_questions: int = Field(default=5, ge=1, le=10)


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