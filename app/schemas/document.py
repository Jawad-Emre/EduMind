from datetime import datetime
from pydantic import BaseModel

from app.db.models import SourceTypeEnum, UploadStatusEnum


class DocumentResponse(BaseModel):
    id: int
    user_id: int
    subject_id: int
    filename: str
    source_type: SourceTypeEnum
    upload_status: UploadStatusEnum
    created_at: datetime

    class Config:
        from_attributes = True