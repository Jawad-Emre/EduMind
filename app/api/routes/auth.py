from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging

from app.api.deps import get_db, get_current_user
from app.db.models import User
from app.schemas.auth import SignupRequest, LoginRequest, TokenResponse, UserMeResponse
from app.core.security import hash_password, verify_password, create_access_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/signup", response_model=TokenResponse, status_code=201)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        logger.info("Signup rejected — email already registered: %s", payload.email)
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        auth_provider="email",
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info("New user signed up: %s (id=%s)", new_user.email, new_user.id)
    token = create_access_token(new_user.id)
    return TokenResponse(access_token=token, user_id=new_user.id)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user is None or user.password_hash is None:
        logger.warning("Login failed — no account for: %s", payload.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(payload.password, user.password_hash):
        logger.warning("Login failed — wrong password for: %s", payload.email)
        raise HTTPException(status_code=401, detail="Invalid email or password")

    logger.info("User logged in: %s (id=%s)", user.email, user.id)
    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user_id=user.id)


@router.get("/me", response_model=UserMeResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user