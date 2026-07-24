from datetime import datetime
from pydantic import BaseModel


class QuizGenerateRequest(BaseModel):
    subject_id: int
    material_id: int | None = None
    session_id: int | None = None
    num_questions: int = 5


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