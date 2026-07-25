# app/api/routes/admin.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.memory.sweep import sweep_stale_sessions

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/sweep-sessions")
async def trigger_sweep(db: AsyncSession = Depends(get_db)):
    count = await sweep_stale_sessions(db)
    return {"closed_sessions": count}

from app.retrieval.vector_store import wipe_collection

@router.post("/debug/wipe-chroma")
async def debug_wipe_chroma():
    result = wipe_collection()
    return result