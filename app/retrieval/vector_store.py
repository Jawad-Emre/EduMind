from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chunk
from app.core.exceptions import ExtractionError


async def add_chunks(db: AsyncSession, chunks: list[dict], material_id: int) -> list[dict]:
    if not chunks:
        raise ExtractionError("No chunks provided to store")

    for c in chunks:
        db.add(Chunk(
            material_id=material_id,
            content=c["content"],
            chunk_index=c["chunk_index"],
            page_number=c["page_number"],
            embedding=c["embedding"],
        ))

    return chunks


async def query_similar(
    db: AsyncSession,
    query_embedding: list[float],
    material_ids: list[int] | None = None,
    top_k: int = 5,
) -> list[dict]:
    stmt = select(Chunk).order_by(Chunk.embedding.cosine_distance(query_embedding)).limit(top_k)

    if material_ids:
        stmt = stmt.where(Chunk.material_id.in_(material_ids))

    result = await db.execute(stmt)
    rows = result.scalars().all()

    matches = []
    for row in rows:
        matches.append({
            "content": row.content,
            "page_number": row.page_number,
            "material_id": row.material_id,
        })
    return matches