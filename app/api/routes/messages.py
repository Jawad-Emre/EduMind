from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_current_user
from app.db.models import Message, ChatSession, User
from app.schemas.message import MessageCreate, MessageResponse

router = APIRouter(prefix="/messages", tags=["messages"])

# --- 45-min inactivity auto-close: DISABLED ---
# Sessions no longer auto-close on inactivity. They stay open so users can
# return to any chat at any time. Summarization is triggered explicitly by the
# "End Session" button (PATCH /sessions/{id}/end) instead.
# INACTIVITY_THRESHOLD = timedelta(minutes=45)
# MIN_WORD_THRESHOLD = 40
#
#
# async def maybe_close_stale_session(session: ChatSession, db: AsyncSession) -> None:
#     if session.ended_at is not None:
#         return
#
#     now = datetime.now(timezone.utc)
#     gap = now - session.last_activity_at
#     if gap <= INACTIVITY_THRESHOLD:
#         return
#
#     result = await db.execute(select(Message).where(Message.session_id == session.id))
#     messages = result.scalars().all()
#     total_words = sum(len(m.content.split()) for m in messages if m.role == RoleEnum.user)
#
#     if total_words >= MIN_WORD_THRESHOLD:
#         session.ended_at = session.last_activity_at
#         await db.commit()
#         await db.refresh(session)
#         await persist_session_summary(session.id, db, refresh=False)


@router.post("/", response_model=MessageResponse, status_code=201)
async def create_message(
    payload: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ChatSession, payload.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your session")

    # Inactivity auto-close disabled — see note above. Sessions stay open.
    # await maybe_close_stale_session(session, db)
    #
    # if session.ended_at is not None:
    #     raise HTTPException(status_code=400, detail="Session has ended due to inactivity. Start a new session.")

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=422, detail="Message content cannot be empty")

    new_message = Message(session_id=payload.session_id, role=payload.role, content=content)
    session.last_activity_at = datetime.now(timezone.utc)

    db.add(new_message)
    await db.commit()
    await db.refresh(new_message)
    return new_message


@router.get("/session/{session_id}", response_model=list[MessageResponse])
async def get_session_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your session")

    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    return result.scalars().all()