from datetime import datetime, timezone
from sqlalchemy import select
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_user
from app.db.models import ChatSession, SubjectProfile, User
from app.schemas.session import SessionCreate, SessionResponse, SessionSummaryResponse
from app.memory.session_store import persist_session_summary
from app.core.exceptions import ExtractionError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.get("/", response_model=list[SessionResponse])
async def list_sessions(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id, ChatSession.subject_id == subject_id)
        .order_by(ChatSession.started_at.desc())
    )
    return result.scalars().all()

@router.post("/", response_model=SessionResponse, status_code=201)
async def create_session(
    payload: SessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subject = await db.get(SubjectProfile, payload.subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail="Subject not found")
    if subject.user_id != current_user.id:
        raise HTTPException(status_code=400, detail="Subject does not belong to this user")

    new_session = ChatSession(user_id=current_user.id, subject_id=payload.subject_id)
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session


@router.patch("/{session_id}/end", response_model=SessionResponse)
async def end_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your session")
    if session.ended_at is not None:
        raise HTTPException(status_code=400, detail="Session already ended")

    session.ended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(session)

    logger.info("Session %s ended by user %s — generating summary.", session.id, current_user.id)
    # Best-effort summary on manual end; never blocks closing the session.
    await persist_session_summary(session.id, db, refresh=False)
    return session


def _summary_to_response(summary) -> SessionSummaryResponse:
    """Build the flat response from a SessionSummary row's structured payload."""
    structured = summary.structured or {}
    return SessionSummaryResponse(
        summary_text=summary.summary_text,
        topics_covered=structured.get("topics_covered", []),
        understood_well=structured.get("understood_well", []),
        struggled_with=structured.get("struggled_with", []),
        review_suggestions=structured.get("review_suggestions", []),
    )


@router.post("/{session_id}/summary", response_model=SessionSummaryResponse)
async def summarize_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your session")

    # refresh=True: (re)generate on demand, works on active or ended sessions.
    logger.info("Summary requested for session %s by user %s.", session.id, current_user.id)
    try:
        summary = await persist_session_summary(session.id, db, refresh=True)
    except ExtractionError as e:
        detail = str(e)
        if "rate_limit_exceeded" in detail or "TPM" in detail or "Requested" in detail:
            logger.warning("Summary hit Groq rate limit (session %s).", session.id)
            raise HTTPException(
                status_code=429,
                detail="The AI is busy right now. Please wait a few seconds and try again.",
            ) from e
        logger.error("Summary generation failed (session %s): %s", session.id, detail)
        raise HTTPException(
            status_code=502,
            detail="We couldn't generate your summary just now. Please try again in a moment.",
        ) from e

    if summary is None:
        logger.info("Summary skipped for session %s — not enough conversation.", session.id)
        raise HTTPException(
            status_code=422,
            detail="Not enough conversation yet to summarize. Chat a bit more and try again.",
        )
    logger.info("Summary generated for session %s.", session.id)
    return _summary_to_response(summary)