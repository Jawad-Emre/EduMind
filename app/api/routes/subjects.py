from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db , get_current_user
from app.db.models import SubjectProfile, User
from app.schemas.subject import SubjectCreate, SubjectResponse

router = APIRouter(prefix="/subjects", tags=["subjects"])


@router.post("/", response_model=SubjectResponse, status_code=201)
async def create_subject(
    payload: SubjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    new_subject = SubjectProfile(
        user_id=current_user.id,
        subject_name=payload.subject_name,
    )
    db.add(new_subject)
    await db.commit()
    await db.refresh(new_subject)
    return new_subject


@router.get("/", response_model=list[SubjectResponse])
async def list_subjects(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(SubjectProfile).where(SubjectProfile.user_id == current_user.id)
    )
    return result.scalars().all()