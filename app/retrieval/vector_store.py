import uuid

import chromadb

from app.core.exceptions import ExtractionError

CHROMA_DIR = "chroma_data"
COLLECTION_NAME = "study_materials"

_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = _client.get_or_create_collection(name=COLLECTION_NAME)
    return _collection


def add_chunks(chunks: list[dict], material_id: int) -> list[dict]:
    """
    Takes embedder output: [{"page_number", "chunk_index", "content", "embedding"}, ...]
    Stores each chunk's embedding in ChromaDB, tagged with metadata for filtering later.
    Returns the same chunks, each with an added "embedding_id" key (str) —
    this is the value that gets saved into the Chunk.embedding_id column in Postgres.
    """
    if not chunks:
        raise ExtractionError("No chunks provided to store in vector database")

    collection = _get_collection()

    ids = [str(uuid.uuid4()) for _ in chunks]
    embeddings = [c["embedding"] for c in chunks]
    documents = [c["content"] for c in chunks]
    metadatas = [
        {
            "material_id": material_id,
            "page_number": c["page_number"],
            "chunk_index": c["chunk_index"],
        }
        for c in chunks
    ]

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    for chunk, chunk_id in zip(chunks, ids):
        chunk["embedding_id"] = chunk_id

    return chunks


def query_similar(query_embedding: list[float], material_ids: list[int] | None = None, top_k: int = 5) -> list[dict]:
    """
    Finds the top_k most similar chunks to a query embedding.
    Optionally restricts the search to specific material_ids (e.g. only this user's documents).
    Returns a list of {"content", "page_number", "material_id", "distance"} dicts.
    """
    collection = _get_collection()

    where_filter = None
    if material_ids:
        where_filter = {"material_id": {"$in": material_ids}}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where_filter,
    )

    matches = []
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for doc, meta, dist in zip(documents, metadatas, distances):
        matches.append({
            "content": doc,
            "page_number": meta.get("page_number"),
            "material_id": meta.get("material_id"),
            "distance": dist,
        })

    return matches