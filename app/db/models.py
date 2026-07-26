import enum
from datetime import datetime

from sqlalchemy import (
    ForeignKey, String, Text, Float, Integer, JSON, DateTime,
    Enum as SAEnum, CheckConstraint, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from pgvector.sqlalchemy import Vector


# ---------- Enums ----------

class LevelEnum(str, enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class RoleEnum(str, enum.Enum):
    user = "user"
    assistant = "assistant"


class UploadStatusEnum(str, enum.Enum):
    processing = "processing"
    ready = "ready"
    failed = "failed"


class SourceTypeEnum(str, enum.Enum):
    pdf = "pdf"
    image = "image"
    docx = "docx"


# ---------- Core tables ----------

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(50), default="email")  # "email" or "google"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    subjects: Mapped[list["SubjectProfile"]] = relationship(back_populates="user")
    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="user")
    materials: Mapped[list["StudyMaterial"]] = relationship(back_populates="user")
    quizzes: Mapped[list["Quiz"]] = relationship(back_populates="user")


class SubjectProfile(Base):
    __tablename__ = "subject_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject_name: Mapped[str] = mapped_column(String(100))
    current_level: Mapped[LevelEnum] = mapped_column(
        SAEnum(LevelEnum), default=LevelEnum.beginner
    )
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0)
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="subjects")
    sessions: Mapped[list["ChatSession"]] = relationship(back_populates="subject")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subject_profiles.id"))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship(back_populates="sessions")
    subject: Mapped["SubjectProfile"] = relationship(back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(back_populates="session")
    summary: Mapped["SessionSummary | None"] = relationship(back_populates="session")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"))
    role: Mapped[RoleEnum] = mapped_column(SAEnum(RoleEnum))
    content: Mapped[str] = mapped_column(Text)
    signals_extracted: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class StudyMaterial(Base):
    __tablename__ = "study_materials"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subject_profiles.id"))
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[SourceTypeEnum] = mapped_column(SAEnum(SourceTypeEnum))
    upload_status: Mapped[UploadStatusEnum] = mapped_column(
        SAEnum(UploadStatusEnum), default=UploadStatusEnum.processing
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="materials")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="material")


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        CheckConstraint("material_id IS NOT NULL", name="chunk_must_have_material"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("study_materials.id"))
    content: Mapped[str] = mapped_column(Text)
    chunk_index: Mapped[int] = mapped_column(Integer)
    embedding_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(384))

    material: Mapped["StudyMaterial"] = relationship(back_populates="chunks")

class SessionSummary(Base):
    __tablename__ = "session_summaries"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), unique=True)
    summary_text: Mapped[str] = mapped_column(Text)
    embedding_id: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped["ChatSession"] = relationship(back_populates="summary")


class Quiz(Base):
    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subject_profiles.id"))
    questions: Mapped[dict] = mapped_column(JSON)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="quizzes")