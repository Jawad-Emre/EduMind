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