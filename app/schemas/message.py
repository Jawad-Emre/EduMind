from datetime import datetime
from pydantic import BaseModel

from app.db.models import RoleEnum


class MessageCreate(BaseModel):
    session_id: int
    role: RoleEnum
    content: str


class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: RoleEnum
    content: str
    created_at: datetime

    class Config:
        from_attributes = True