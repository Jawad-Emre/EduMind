from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_current_user
from app.db.models import Quiz, User, SubjectProfile, StudyMaterial, Chunk, ChatSession, Message
from app.schemas.quiz import QuizGenerateRequest, QuizSubmitRequest, QuizResponse
from app.quiz.quiz_generator import generate_quiz_questions, score_quiz_attempt
from app.profiling.level_detector import update_confidence_from_quiz, score_to_level
from app.core.exceptions import ExtractionError

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


@router.post("/generate", response_model=QuizResponse, status_code=201)
async def generate_quiz(
    payload: QuizGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subject = await db.get(SubjectProfile, payload.subject_id)
    if subject is None or subject.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Subject not found for this user")

    if payload.material_id is not None:
        material = await db.get(StudyMaterial, payload.material_id)
        if material is None or material.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Material not found for this user")

        result = await db.execute(
            select(Chunk).where(Chunk.material_id == payload.material_id).order_by(Chunk.chunk_index)
        )
        chunks = result.scalars().all()
        if not chunks:
            raise HTTPException(status_code=422, detail="Material has no processed content yet")

        source_text = " ".join(c.content for c in chunks)

    elif payload.session_id is not None:
        session = await db.get(ChatSession, payload.session_id)
        if session is None or session.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Session not found for this user")

        result = await db.execute(
            select(Message).where(Message.session_id == payload.session_id).order_by(Message.created_at)
        )
        msgs = result.scalars().all()
        if not msgs:
            raise HTTPException(status_code=422, detail="Session has no messages yet")

        source_text = " ".join(m.content for m in msgs)

    else:
        raise HTTPException(status_code=422, detail="Provide either material_id or session_id")

    try:
        questions = generate_quiz_questions(source_text, payload.num_questions)
    except ExtractionError as e:
        raise HTTPException(status_code=502, detail=f"Quiz generation failed: {e}")

    new_quiz = Quiz(
        user_id=current_user.id,
        subject_id=payload.subject_id,
        questions=questions,
        score=None,
    )
    db.add(new_quiz)
    await db.commit()
    await db.refresh(new_quiz)
    return new_quiz


@router.post("/{quiz_id}/submit", response_model=QuizResponse)
async def submit_quiz(
    quiz_id: int,
    payload: QuizSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    quiz = await db.get(Quiz, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your quiz")
    if quiz.score is not None:
        raise HTTPException(status_code=400, detail="Quiz already submitted")

    try:
        score = score_quiz_attempt(quiz.questions, payload.answers)
    except ExtractionError as e:
        raise HTTPException(status_code=422, detail=str(e))

    quiz.score = score
    subject = await db.get(SubjectProfile, quiz.subject_id)
    passed = score >= 0.6
    subject.confidence_score = update_confidence_from_quiz(subject.confidence_score, passed)
    subject.current_level = score_to_level(subject.confidence_score)

    await db.commit()
    await db.refresh(quiz)
    return quiz