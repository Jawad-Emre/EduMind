from datetime import datetime
from pydantic import BaseModel


class SessionCreate(BaseModel):
    subject_id: int


class SessionResponse(BaseModel):
    id: int
    user_id: int
    subject_id: int
    started_at: datetime
    last_activity_at: datetime
    ended_at: datetime | None

    class Config:
        from_attributes = True


class SessionSummaryResponse(BaseModel):
    summary_text: str
    topics_covered: list[str] = []
    understood_well: list[str] = []
    struggled_with: list[str] = []
    review_suggestions: list[str] = []