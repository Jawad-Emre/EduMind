import asyncio
import json
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatSession, Message, SessionSummary, SubjectProfile, RoleEnum
from app.generation.llm_client import generate_response
from app.core.exceptions import ExtractionError

# Cap on how many strengths/struggles we keep per subject — keeps the profile
# compact and cheap to inject into every prompt.
_PROFILE_LIST_CAP = 10

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = (
    "You are EduMind, an expert AI tutor and study assistant.\n\n"

    "Your task is to create high-quality revision notes for students based ONLY on "
    "the tutoring conversation.\n\n"

    "These notes are meant for the student to review later before quizzes, exams, "
    "or future study sessions.\n\n"

    "Do NOT describe the conversation.\n"
    "Do NOT mention the student, EduMind, questions, or discussion.\n"
    "Focus only on the academic knowledge that was learned.\n\n"

    "Return ONLY valid JSON and nothing else."
)

SUMMARY_PROMPT_TEMPLATE = (
    "Read the tutoring conversation below and generate a structured study summary.\n\n"

    "IMPORTANT RULES:\n"
    "- Write revision notes, not a conversation recap.\n"
    "- Never write sentences like:\n"
    "  * The student asked...\n"
    "  * EduMind explained...\n"
    "  * The discussion covered...\n"
    "  * During this session...\n"
    "- Explain the KNOWLEDGE itself.\n"
    "- Use clear educational language.\n"
    "- Only include information that actually appears in the conversation.\n"
    "- Do not invent new concepts.\n\n"

    "RELEVANCE CHECK — do this FIRST, before anything else:\n"
    "- Decide whether the conversation contains genuine academic learning about "
    "the subject that is worth remembering in the student's long-term profile.\n"
    "- Set \"profile_relevant\" to true ONLY when it does.\n"
    "- Set \"profile_relevant\" to false for greetings, small talk, test messages, "
    "file/administrative questions, or anything with no real subject learning "
    "(e.g. 'hi', 'what file is this', 'my recommendation letter').\n"
    "- When \"profile_relevant\" is false, return EMPTY arrays for "
    "understood_well and struggled_with.\n\n"

    "Return ONLY valid JSON using EXACTLY this schema:\n\n"

    "{{\n"
    '  "profile_relevant": true,\n'
    '  "summary_text": "Markdown study notes.",\n'
    '  "topics_covered": ["topic"],\n'
    '  "understood_well": ["concept"],\n'
    '  "struggled_with": ["concept"],\n'
    '  "review_suggestions": ["revision suggestion"]\n'
    "}}\n\n"

    "The summary_text MUST:\n"
    "- NOT start with '# Chat Summary' because the frontend already displays the title.\n"
    "- Be written in Markdown.\n"
    "- Contain these sections whenever applicable:\n\n"

    "## Topic\n"
    "Briefly state the subject.\n\n"

    "## What You Learned\n"
    "Explain the important concepts clearly.\n\n"

    "## Key Points\n"
    "Use bullet points.\n\n"

    "## Main Takeaway\n"
    "Summarize the most important concept in one short paragraph.\n\n"

    "Do NOT include:\n"
    "- Topics Covered\n"
    "- Concepts Understood Well\n"
    "- Concepts to Review\n"
    "- Review Suggestions\n"
    "These are returned separately in JSON fields.\n\n"

    "For the remaining JSON fields:\n"
    "- profile_relevant: true only if the conversation has real academic "
    "learning worth saving to the student's profile (see RELEVANCE CHECK above).\n"
    "- topics_covered: list the major topics.\n"
    "- understood_well: concepts the student demonstrated understanding of.\n"
    "- struggled_with: concepts the student seemed confused about.\n"
    "- review_suggestions: short revision recommendations.\n\n"

    "CONVERSATION:\n{conversation}"
)

# Keys we expect back from the model; used to normalise the parsed object.
_LIST_FIELDS = ("topics_covered", "understood_well", "struggled_with", "review_suggestions")


def _build_transcript(messages: list[Message]) -> str:
    return "\n".join(
        f"{'Student' if m.role == RoleEnum.user else 'EduMind'}: {m.content}"
        for m in messages
    )


def _parse_summary_json(raw_response: str) -> dict:
    """Strip code fences and parse the model's JSON reply.

    Mirrors the defensive parsing used in app/quiz/quiz_generator.py.
    Raises ExtractionError on anything unusable.
    """
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ExtractionError(f"Summary generation returned invalid JSON: {e}")

    if not isinstance(data, dict):
        raise ExtractionError("Summary generation did not return a JSON object")

    # Normalise: guarantee the shape callers rely on.
    summary_text = data.get("summary_text")
    if not isinstance(summary_text, str) or not summary_text.strip():
        raise ExtractionError("Summary generation returned no summary_text")

    normalised: dict = {"summary_text": summary_text.strip()}

    # Relevance gate for profile updates. Accept a real bool or a "true"/"false"
    # string. Default to False when missing/unusable so junk chat never pollutes
    # the profile — a real learning session must be explicitly flagged relevant.
    raw_relevant = data.get("profile_relevant", False)
    if isinstance(raw_relevant, bool):
        normalised["profile_relevant"] = raw_relevant
    else:
        normalised["profile_relevant"] = str(raw_relevant).strip().lower() == "true"

    for field in _LIST_FIELDS:
        value = data.get(field, [])
        if not isinstance(value, list):
            value = []
        # Keep only non-empty strings.
        normalised[field] = [str(item).strip() for item in value if str(item).strip()]
    return normalised


async def build_structured_summary(session_id: int, db: AsyncSession) -> dict | None:
    """Generate a structured recap of a session.

    Returns a dict with keys: summary_text, topics_covered, understood_well,
    struggled_with, review_suggestions.

    Returns None only when there is genuinely nothing to summarize (no
    messages). Raises ExtractionError when generation or JSON parsing fails,
    so callers can tell a real failure (rate limit, bad JSON) apart from an
    empty session and surface an appropriate message.
    """
    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    messages = result.scalars().all()
    if not messages:
        return None

    prompt = [
        {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
        {"role": "user", "content": SUMMARY_PROMPT_TEMPLATE.format(
            conversation=_build_transcript(messages)
        )},
    ]

    try:
        # generate_response is a blocking (sync) network call — keep it off the event loop.
        raw = await asyncio.to_thread(generate_response, prompt, 2500)
        return _parse_summary_json(raw)
    except ExtractionError as e:
        # Generation or JSON parsing failed. Log the real cause and re-raise so
        # callers can distinguish this from a genuinely empty session (None).
        logger.warning("Summary generation failed for session %s: %s", session_id, e)
        raise


def _merge_list(existing: list[str], new_items: list[str], cap: int = _PROFILE_LIST_CAP) -> list[str]:
    """Union with newest-first ordering, case-insensitive dedupe, capped length.

    New items are considered newer, so they take precedence and appear first.
    Original casing of the first occurrence is preserved.
    """
    merged: list[str] = []
    seen: set[str] = set()
    for item in list(new_items) + list(existing):
        key = item.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(item.strip())
        if len(merged) >= cap:
            break
    return merged


def merge_knowledge_state(existing: dict | None, summary: dict) -> dict:
    """Fold a fresh structured summary into the evolving per-subject profile.

    Pure/deterministic — no LLM. Shape:
      {"strengths": [...], "struggles": [...], "notes": "..."}
    """
    existing = existing or {}
    old_strengths = existing.get("strengths") or []
    old_struggles = existing.get("struggles") or []

    strengths = _merge_list(old_strengths, summary.get("understood_well", []))
    struggles = _merge_list(old_struggles, summary.get("struggled_with", []))

    # A concept the student now understands should no longer be flagged as a struggle.
    strength_keys = {s.lower() for s in strengths}
    struggles = [s for s in struggles if s.lower() not in strength_keys]

    topics = summary.get("topics_covered", [])
    if topics:
        notes = "Last session covered: " + ", ".join(topics[:3])
    else:
        notes = existing.get("notes", "")

    return {"strengths": strengths, "struggles": struggles, "notes": notes}


async def persist_session_summary(
    session_id: int,
    db: AsyncSession,
    *,
    refresh: bool = False,
) -> SessionSummary | None:
    """Build, store, and fold a session summary into the learner profile.

    - refresh=False (auto path: session end / inactivity sweep): if a summary
      already exists, do nothing and return None.
    - refresh=True (summary button): regenerate and overwrite the existing row.

    Returns the persisted SessionSummary, or None if there was nothing to
    summarize. On the auto paths (refresh=False) a generation/parse failure is
    swallowed (returns None) so closing a session never blocks. On the on-demand
    button path (refresh=True) that failure is propagated as ExtractionError so
    the endpoint can return a meaningful error to the user.
    """
    session = await db.get(ChatSession, session_id)
    if session is None:
        return None

    existing_result = await db.execute(
        select(SessionSummary).where(SessionSummary.session_id == session_id)
    )
    existing_summary = existing_result.scalar_one_or_none()

    if existing_summary is not None and not refresh:
        return None  # already summarized; auto path avoids duplicate work

    try:
        structured = await build_structured_summary(session_id, db)
    except ExtractionError:
        # Generation failed (rate limit, invalid JSON, etc.). The real cause was
        # already logged in build_structured_summary. On the best-effort auto
        # paths we swallow so closing never blocks; on the button path we
        # propagate so the endpoint can surface it to the user.
        if refresh:
            raise
        return None
    if structured is None:
        return None  # genuinely nothing to summarize (no messages)

    if existing_summary is not None:
        existing_summary.summary_text = structured["summary_text"]
        existing_summary.structured = structured
        summary_row = existing_summary
    else:
        summary_row = SessionSummary(
            session_id=session_id,
            summary_text=structured["summary_text"],
            structured=structured,
        )
        db.add(summary_row)

    # Fold into the subject's evolving knowledge_state so future chats adapt —
    # but only when the model judged the conversation academically relevant.
    # Irrelevant chats (greetings, small talk, admin questions) still get a
    # stored summary, but must not pollute the long-term profile.
    if structured.get("profile_relevant"):
        subject = await db.get(SubjectProfile, session.subject_id)
        if subject is not None:
            subject.knowledge_state = merge_knowledge_state(subject.knowledge_state, structured)
            logger.info(
                "Session %s judged RELEVANT — profile updated (strengths=%s, struggles=%s).",
                session_id,
                structured.get("understood_well", []),
                structured.get("struggled_with", []),
            )
    else:
        logger.info(
            "Session %s judged NOT relevant — profile update skipped.",
            session_id,
        )

    await db.commit()
    await db.refresh(summary_row)
    return summary_row
