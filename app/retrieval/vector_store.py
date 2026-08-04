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

from sentence_transformers import CrossEncoder

_reranker = None  # loaded once, reused across calls


def _get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker


def rerank_chunks(query_text: str, chunks: list[dict], top_k: int) -> list[dict]:
    """
    Re-scores retrieved chunks against the query using a cross-encoder,
    then returns the top_k most relevant — more accurate than raw
    cosine similarity alone since query and chunk are compared together.
    """
    if not chunks:
        return []

    reranker = _get_reranker()
    pairs = [(query_text, chunk["content"]) for chunk in chunks]
    scores = reranker.predict(pairs)

    for chunk, score in zip(chunks, scores):
        chunk["rerank_score"] = float(score)

    ranked = sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)
    return ranked[:top_k]

async def query_similar(
    db: AsyncSession,
    query_embedding: list[float],
    material_ids: list[int] | None = None,
    top_k: int = 20,
) -> list[dict]:
    distance = Chunk.embedding.cosine_distance(query_embedding).label("distance")

    stmt = select(Chunk, distance).order_by(distance).limit(top_k)

    if material_ids:
        stmt = stmt.where(Chunk.material_id.in_(material_ids))

    result = await db.execute(stmt)
    rows = result.all()  # each row is a (Chunk, distance) tuple now

    matches = []
    for chunk, dist in rows:
        matches.append({
            "content": chunk.content,
            "page_number": chunk.page_number,
            "material_id": chunk.material_id,
            "distance": dist,
        })
    return matches