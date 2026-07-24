from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.db.models import User
from app.schemas.user import UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(db: AsyncSession = Depends(get_db)):
    new_user = User()
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user