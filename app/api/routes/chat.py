from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_current_user
from app.db.models import ChatSession, Message, RoleEnum, SubjectProfile, StudyMaterial, User
from app.ingestion.embedder import embed_chunks
from app.retrieval.vector_store import query_similar
from app.generation.prompt_builder import build_prompt
from app.generation.llm_client import generate_response
from app.core.exceptions import ExtractionError
from app.profiling.level_detector import score_message_signal, update_confidence_from_message, score_to_level

router = APIRouter(prefix="/chat", tags=["chat"])


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

    query_embedding = embed_chunks([{"content": content, "page_number": 0, "chunk_index": 0}])[0]["embedding"]
    retrieved = query_similar(query_embedding, material_ids=user_material_ids, top_k=5) if user_material_ids else []

    result = await db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.created_at)
    )
    history = [{"role": m.role.value, "content": m.content} for m in result.scalars().all()]

    has_materials = bool(user_material_ids)
    prompt = build_prompt(subject.current_level, retrieved, history, content, has_materials)

    try:
        answer = generate_response(prompt, max_tokens=6000)
    except ExtractionError as e:
        detail = str(e)
        if "rate_limit_exceeded" in detail or "TPM" in detail or "Requested" in detail:
            raise HTTPException(
                status_code=429,
                detail="Groq request limit reached. Please wait a moment and try again.",
            ) from e
        raise HTTPException(status_code=502, detail=f"Response generation failed: {detail}") from e

    user_msg = Message(session_id=session.id, role=RoleEnum.user, content=content)
    assistant_msg = Message(session_id=session.id, role=RoleEnum.assistant, content=answer)
    db.add(user_msg)
    db.add(assistant_msg)

    signal_score = score_message_signal(content)
    new_score, _ = update_confidence_from_message(subject.confidence_score, signal_score, None)
    subject.confidence_score = new_score
    subject.current_level = score_to_level(new_score)

    await db.commit()
    return ChatResponse(answer=answer, level_used=subject.current_level.value)