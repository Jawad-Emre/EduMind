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
from app.db.models import StudyMaterial, SubjectProfile, User, SourceTypeEnum, UploadStatusEnum
from app.schemas.document import DocumentResponse
from app.ingestion.pdf_extractor import extract_text_from_pdf
from app.ingestion.chunker import chunk_pages
from app.ingestion.embedder import embed_chunks
from app.retrieval.vector_store import add_chunks
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])

MAX_FILE_SIZE = 20 * 1024 * 1024 #20MB
STORAGE_BUCKET = "study-materials"

supabase = create_client(settings.supabase_url, settings.supabase_service_key)

MAGIC_MAP = {
    "application/pdf": SourceTypeEnum.pdf,
    # "image/png": SourceTypeEnum.image,
    # "image/jpeg": SourceTypeEnum.image,
    # "application/vnd.openxmlformats-officedocument.wordprocessingml.document": SourceTypeEnum.docx,
}

EXTENSION_MAP = {
    ".pdf": SourceTypeEnum.pdf,
    # ".docx": SourceTypeEnum.docx,
    # ".png": SourceTypeEnum.image,
    # ".jpg": SourceTypeEnum.image,
    # ".jpeg": SourceTypeEnum.image,
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
            chunks = await asyncio.to_thread(chunk_pages, pages) 
            embedded = await asyncio.to_thread(embed_chunks, chunks)
            await add_chunks(db, embedded, material_id=material_id)


            material.upload_status = UploadStatusEnum.ready

            await db.commit()
            logger.info("Document ready: material %s (%d chunks).", material_id, len(embedded))

        except ExtractionError as e:

            logger.warning("Extraction failed: %s", e)

            await db.rollback()

            material.upload_status = UploadStatusEnum.failed

            await db.commit()

        except Exception:

            logger.exception("Document processing failed")

            await db.rollback()

            material.upload_status = UploadStatusEnum.failed

            await db.commit()

            # cleanup uploaded file
            try:
                await asyncio.to_thread(
                    supabase.storage.from_(STORAGE_BUCKET).remove,
                    [material.stored_path],
                )
            except Exception:
                logger.exception("Failed removing orphaned Supabase file")


@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    subject_id: int = Form(...),
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify subject exists
    subject = await db.get(SubjectProfile, subject_id)

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail="Subject not found",
        )
    # Verify ownership
    if subject.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not your subject",
        )
    
    # 3. Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in EXTENSION_MAP:
        raise HTTPException(status_code=422, detail=f"Unsupported file type '{ext}'")

    # Read file
    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(status_code=422, detail="Uploaded file is empty")
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 20MB size limit")

    # Verify real MIME type
    detected_mime = magic.from_buffer(contents, mime=True)
    if detected_mime not in MAGIC_MAP:
        raise HTTPException(status_code=422, detail=f"Unrecognized content type: {detected_mime}")

    if EXTENSION_MAP.get(ext) != MAGIC_MAP[detected_mime]:
        raise HTTPException(status_code=422, detail="File extension does not match actual file content")

      # Build storage path
    stored_filename = f"{uuid.uuid4()}{ext}"
    stored_path = f"{current_user.id}/{stored_filename}"

    # Upload to Supabase
    try:
        await asyncio.to_thread(
            supabase.storage.from_(STORAGE_BUCKET).upload,
            stored_path,
            contents,
            file_options={
                "content-type": detected_mime,
            },
        )

    except Exception as e:

        logger.exception("Supabase upload failed")

        raise HTTPException(
            status_code=500,
            detail="Failed to upload document",
        ) from e

     # Create database row
    try:
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
    except Exception:

        await db.rollback()

        logger.exception("Database insert failed")

        # remove uploaded file
        try:
            await asyncio.to_thread(
                supabase.storage.from_(STORAGE_BUCKET).remove,
                [stored_path],
            )
        except Exception:
            logger.exception("Failed cleaning orphaned file")

        raise HTTPException(
            status_code=500,
            detail="Failed to register uploaded document",
        )
     # Background processing
    background_tasks.add_task(process_document_pipeline, new_material.id, contents, new_material.source_type)
    logger.info("Upload accepted: '%s' (material %s) by user %s — processing.", file.filename, new_material.id, current_user.id)
    return new_material
    


@router.get("/{document_id}/status", response_model=DocumentResponse)
async def get_document_status(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(StudyMaterial).where(
            StudyMaterial.id == document_id,
            StudyMaterial.user_id == current_user.id,
        )
    )

    material = result.scalar_one_or_none()

    if material is None:
        raise HTTPException(
            status_code=404,
            detail="Document not found",
        )

    return material

@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    subject_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    subject = await db.get(SubjectProfile, subject_id)

    if subject is None:
        raise HTTPException(
            status_code=404,
            detail="Subject not found",
        )

    if subject.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Not your subject",
        )

    result = await db.execute(
        select(StudyMaterial)
        .where(StudyMaterial.subject_id == subject_id)
        .order_by(StudyMaterial.created_at.desc())
    )

    return result.scalars().all()