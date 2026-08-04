from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import asyncio
import logging

from app.api.deps import get_db, get_current_user
from app.db.models import ChatSession, Message, RoleEnum, SubjectProfile, StudyMaterial, User
from app.ingestion.embedder import embed_chunks
from app.retrieval.vector_store import query_similar, rerank_chunks
from app.generation.prompt_builder import build_prompt
from app.generation.llm_client import generate_response
from app.core.exceptions import ExtractionError
from app.profiling.level_detector import (
    score_message_signal,
    update_confidence_from_message,
    score_to_level,
    apply_decay,
)

router = APIRouter(prefix="/chat", tags=["chat"])

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    session_id: int
    content: str


class ChatResponse(BaseModel):
    answer: str
    level_used: str


@router.post("/", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ChatSession, payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your session")
    if session.ended_at is not None:
        raise HTTPException(status_code=400, detail="Session has ended")

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content cannot be empty")

    logger.info("Chat: user %s -> session %s (%d chars)", current_user.id, session.id, len(content))

    subject = await db.get(SubjectProfile, session.subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject profile not found")

    result = await db.execute(
        select(StudyMaterial.id).where(
            StudyMaterial.user_id == session.user_id,
            StudyMaterial.subject_id == session.subject_id,
        )
    )
    user_material_ids = [row[0] for row in result.all()]

    embedded = await asyncio.to_thread(
        embed_chunks, [{"content": content, "page_number": 0, "chunk_index": 0}]
    )
    query_embedding = embedded[0]["embedding"]
    retrieved = (
        await query_similar(db, query_embedding, material_ids=user_material_ids, top_k=20)
        if user_material_ids
        else []
    )

    if retrieved:
        retrieved = rerank_chunks(content, retrieved, top_k=7)

    result = await db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.created_at)
    )
    history = [{"role": m.role.value, "content": m.content} for m in result.scalars().all()]

    has_materials = bool(user_material_ids)
    prompt = build_prompt(
        subject.current_level,
        retrieved,
        history,
        content,
        has_materials,
        learner_memory=subject.knowledge_state,
    )

    # Persist the user's message before generating, so it isn't lost if the
    # LLM call fails. Commit now; the assistant reply is added after generation.
    user_msg = Message(
        session_id=session.id,
        role=RoleEnum.user,
        content=content,
    )
    db.add(user_msg)
    session.last_activity_at = datetime.now(timezone.utc)
    await db.commit()

    try:
        answer = await asyncio.to_thread(generate_response, prompt, 6000)
    except ExtractionError as e:
        await db.rollback()
        detail = str(e)
        if "rate_limit_exceeded" in detail or "TPM" in detail or "Requested" in detail:
            logger.warning("Groq rate limit reached on chat (session %s, user %s)", session.id, current_user.id)
            raise HTTPException(
                status_code=429,
                detail="Groq request limit reached. Please wait a moment and try again.",
            ) from e
        logger.error("Chat generation failed (session %s): %s", session.id, detail)
        raise HTTPException(status_code=502, detail=f"Response generation failed: {detail}") from e

    assistant_msg = Message(
        session_id=session.id,
        role=RoleEnum.assistant,
        content=answer,
    )
    db.add(assistant_msg)

    # Lower a stale score before scoring this message (revives decay).
    subject.confidence_score = apply_decay(subject.confidence_score, subject.last_updated)

    signal_score = score_message_signal(content)
    new_score, new_spike = update_confidence_from_message(
        subject.confidence_score, signal_score, subject.pending_spike
    )
    subject.confidence_score = new_score
    subject.pending_spike = new_spike
    subject.current_level = score_to_level(new_score)
    subject.last_updated = datetime.now(timezone.utc)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise

    logger.info("Chat: replied in session %s (level=%s)", session.id, subject.current_level.value)
    return ChatResponse(
        answer=answer,
        level_used=subject.current_level.value,
    )