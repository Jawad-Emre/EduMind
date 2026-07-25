import asyncio
import os
import uuid
import magic
from sqlalchemy import select

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Form
from sqlalchemy.ext.asyncio import AsyncSession
from supabase import create_client

from app.api.deps import get_db, get_current_user
from app.core.config import settings
from app.core.exceptions import ExtractionError
from app.db.session import AsyncSessionLocal
from app.db.models import StudyMaterial, User, Chunk, SourceTypeEnum, UploadStatusEnum
from app.schemas.document import DocumentResponse
from app.ingestion.pdf_extractor import extract_text_from_pdf
from app.ingestion.chunker import chunk_pages
from app.ingestion.embedder import embed_chunks
from app.retrieval.vector_store import add_chunks

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 20 * 1024 * 1024
STORAGE_BUCKET = "study-materials"

supabase = create_client(settings.supabase_url, settings.supabase_service_key)

MAGIC_MAP = {
    "application/pdf": SourceTypeEnum.pdf,
    "image/png": SourceTypeEnum.image,
    "image/jpeg": SourceTypeEnum.image,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": SourceTypeEnum.docx,
}

EXTENSION_MAP = {
    ".pdf": SourceTypeEnum.pdf,
    ".docx": SourceTypeEnum.docx,
    ".png": SourceTypeEnum.image,
    ".jpg": SourceTypeEnum.image,
    ".jpeg": SourceTypeEnum.image,
}


async def process_document_pipeline(material_id: int, file_bytes: bytes, source_type: SourceTypeEnum):
    async with AsyncSessionLocal() as db:
        material = await db.get(StudyMaterial, material_id)
        if material is None:
            return
        try:
            if source_type != SourceTypeEnum.pdf:
                raise ExtractionError(f"Ingestion for source_type={source_type} not yet implemented")

            pages = await asyncio.to_thread(extract_text_from_pdf, file_bytes)
            chunks = chunk_pages(pages)  # keep sync if it's pure CPU-light string work
            embedded = await asyncio.to_thread(embed_chunks, chunks)
            stored = await add_chunks(db, embedded, material_id=material_id)


            material.upload_status = UploadStatusEnum.ready
            await db.commit()
        except ExtractionError:
            material.upload_status = UploadStatusEnum.failed
            await db.commit()
        except Exception:
            material.upload_status = UploadStatusEnum.failed
            await db.commit()
            raise


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    subject_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in EXTENSION_MAP:
        raise HTTPException(status_code=422, detail=f"Unsupported file type '{ext}'")

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 20MB size limit")

    detected_mime = magic.from_buffer(contents, mime=True)
    if detected_mime not in MAGIC_MAP:
        raise HTTPException(status_code=422, detail=f"Unrecognized content type: {detected_mime}")

    if EXTENSION_MAP.get(ext) != MAGIC_MAP[detected_mime]:
        raise HTTPException(status_code=422, detail="File extension does not match actual file content")

    stored_filename = f"{uuid.uuid4()}{ext}"
    stored_path = f"{current_user.id}/{stored_filename}"

    await asyncio.to_thread(
        supabase.storage.from_(STORAGE_BUCKET).upload,
        stored_path, contents, file_options={"content-type": detected_mime},
    )

    new_material = StudyMaterial(
        user_id=current_user.id,
        subject_id=subject_id,
        filename=file.filename,
        stored_path=stored_path,
        source_type=EXTENSION_MAP[ext],
        upload_status=UploadStatusEnum.processing,
    )
    db.add(new_material)
    await db.commit()
    await db.refresh(new_material)

    background_tasks.add_task(process_document_pipeline, new_material.id, contents, new_material.source_type)
    return new_material


@router.get("/{document_id}/status", response_model=DocumentResponse)
async def get_document_status(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(StudyMaterial, document_id)
    if material is None:
        raise HTTPException(status_code=404, detail="Document not found")
    if material.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your document")
    return material

@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StudyMaterial).where(
            StudyMaterial.user_id == current_user.id,
            StudyMaterial.subject_id == subject_id,
        )
    )
    return result.scalars().all()