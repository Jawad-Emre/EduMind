from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatSession, Message, RoleEnum
from app.memory.session_store import persist_session_summary

INACTIVITY_THRESHOLD = timedelta(minutes=45)
MIN_WORD_THRESHOLD = 50


async def sweep_stale_sessions(db: AsyncSession) -> int:
    """
    Finds all still-open sessions that have gone stale (inactive past threshold)
    and closes them, triggering summary generation where substance warrants it.
    Meant to be run periodically (e.g. every few hours), not on every request.
    Returns the count of sessions closed.
    """
    now = datetime.now(timezone.utc)
    cutoff = now - INACTIVITY_THRESHOLD

    result = await db.execute(
        select(ChatSession).where(
            ChatSession.ended_at.is_(None),
            ChatSession.last_activity_at < cutoff,
        )
    )
    stale_sessions = result.scalars().all()

    closed_count = 0
    for session in stale_sessions:
        msg_result = await db.execute(
            select(Message).where(Message.session_id == session.id)
        )
        messages = msg_result.scalars().all()
        total_words = sum(
            len(m.content.split()) for m in messages if m.role == RoleEnum.user
        )

        session.ended_at = session.last_activity_at
        await db.commit()
        await db.refresh(session)
        closed_count += 1

        if total_words >= MIN_WORD_THRESHOLD:
            await persist_session_summary(session.id, db, refresh=False)

    return closed_count