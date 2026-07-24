from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatSession, Message, SessionSummary, RoleEnum
from app.ingestion.embedder import embed_chunks
from app.retrieval.vector_store import add_chunks
from app.generation.llm_client import generate_response
from app.core.exceptions import ExtractionError

SUMMARY_PROMPT_TEMPLATE = (
    "Summarize the following tutoring conversation in 5-7 sentences, focusing on: "
    "what topics were covered, what the student seemed to understand well, and what "
    "they seemed confused about. Be concise and factual.\n\n"
    "CONVERSATION:\n{conversation}"
)


async def generate_session_summary(session_id: int, db: AsyncSession) -> SessionSummary | None:
    """
    Generates and stores a SessionSummary for a closed session.
    Returns None if the session has no messages worth summarizing (safety guard —
    should already be filtered by the substance gate in messages.py, but double-checked here).
    """
    existing = await db.execute(
        select(SessionSummary).where(SessionSummary.session_id == session_id)
    )
    if existing.scalar_one_or_none() is not None:
        return None  # already summarized, avoid duplicate work

    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    messages = result.scalars().all()
    if not messages:
        return None

    conversation_text = "\n".join(
        f"{'Student' if m.role == RoleEnum.user else 'EduMind'}: {m.content}"
        for m in messages
    )

    prompt = [
        {"role": "system", "content": "You are a concise summarizer for tutoring sessions."},
        {"role": "user", "content": SUMMARY_PROMPT_TEMPLATE.format(conversation=conversation_text)},
    ]

    try:
        summary_text = generate_response(prompt)
    except ExtractionError:
        return None  # generation failed — don't block session closure on this

    embedded = embed_chunks([{"content": summary_text, "page_number": 0, "chunk_index": 0}])
    stored = add_chunks(embedded, material_id=-session_id)  # negative id namespaces summaries away from real materials
    embedding_id = stored[0]["embedding_id"]

    summary = SessionSummary(
        session_id=session_id,
        summary_text=summary_text,
        embedding_id=embedding_id,
    )
    db.add(summary)
    await db.commit()
    await db.refresh(summary)
    return summary