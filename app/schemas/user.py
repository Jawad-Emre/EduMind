from datetime import datetime
from pydantic import BaseModel


class UserCreate(BaseModel):
    pass  # no input needed — users are anonymous


class UserResponse(BaseModel):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True  # allows reading directly from a SQLAlchemy object