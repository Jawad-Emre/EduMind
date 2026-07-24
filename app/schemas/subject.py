from datetime import datetime
from pydantic import BaseModel

from app.db.models import LevelEnum


class SubjectCreate(BaseModel):
    subject_name: str


class SubjectResponse(BaseModel):
    id: int
    user_id: int
    subject_name: str
    current_level: LevelEnum
    confidence_score: float
    last_updated: datetime

    class Config:
        from_attributes = True