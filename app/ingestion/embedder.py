from sentence_transformers import SentenceTransformer

from app.core.exceptions import ExtractionError

_model = None  # loaded once, reused across calls — avoids reloading the model every time


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("BAAI/bge-base-en-v1.5")
    return _model


def embed_chunks(chunks: list[dict], batch_size: int = 32) -> list[dict]:
    """
    Takes chunker output: [{"page_number": int, "chunk_index": int, "content": str}, ...]
    Returns the same chunks, each with an added "embedding" key (list[float]).
    """
    if not chunks:
        raise ExtractionError("No chunks provided for embedding")

    model = _get_model()
    texts = [c["content"] for c in chunks]

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = embedding.tolist()

    return chunks