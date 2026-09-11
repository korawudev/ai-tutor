from typing import List, Optional
from uuid import UUID
from pathlib import Path
import hashlib
import uuid as uuidlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, Header, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Document, DocumentResponse, DocumentImport, DocumentCreate, ImportResult
from shared.database import get_db
from shared.utils import decode_access_token
from ..services import batch_import, check_duplicate, process_document, retry_document

router = APIRouter(prefix="/api/documents", tags=["documents"])

UPLOAD_DIR = Path("/app/storage/uploads")


async def get_user_id_dependency(authorization: str = Header(None)) -> UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return UUID(payload["sub"])


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    tags: str = Form(""),
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")

    filename = file.filename or "upload.txt"
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        from io import BytesIO
        from pypdf import PdfReader
        try:
            reader = PdfReader(BytesIO(raw))
            parts = [page.extract_text() or "" for page in reader.pages]
            content = "\n".join(parts).strip()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"PDF parse failed: {e}")
    elif suffix in (".txt", ".md", ".markdown"):
        try:
            content = raw.decode("utf-8").strip()
        except UnicodeDecodeError:
            content = raw.decode("gbk", errors="replace").strip()
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix}")

    if not content:
        raise HTTPException(status_code=400, detail="No text extracted from file")

    existing = await check_duplicate(db, user_id, "file", content=content)
    if existing:
        raise HTTPException(status_code=409, detail=f"文档 '{existing.title}' 已存在（相同内容）")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = f"{uuidlib.uuid4().hex}_{Path(filename).name}"
    file_path = UPLOAD_DIR / safe_name
    file_path.write_bytes(raw)

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    document = await process_document(
        db, user_id, "file",
        file_path=str(file_path),
        content=content,
        title=Path(filename).stem,
        tags=tag_list
    )
    if document.status == "failed":
        raise HTTPException(status_code=422, detail=f"文档处理失败: {document.error_message}")
    return DocumentResponse.model_validate(document)


@router.post("/import", response_model=ImportResult)
async def import_documents(
    import_data: DocumentImport,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    result = await batch_import(db, user_id, import_data.sources, import_data.tags, import_data.on_duplicate)
    return ImportResult(**result)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    document_data: DocumentCreate,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    document = await process_document(
        db, user_id, document_data.source_type,
        source_url=document_data.source_url, content=document_data.content,
        title=document_data.title, tags=document_data.tags
    )
    return DocumentResponse.model_validate(document)


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    status: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    query = select(Document).where(Document.user_id == user_id, Document.deleted_at.is_(None))
    if status:
        query = query.where(Document.status == status)
    query = query.order_by(Document.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return [DocumentResponse.model_validate(d) for d in result.scalars().all()]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id, Document.deleted_at.is_(None))
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse.model_validate(document)


@router.post("/retry/{document_id}", response_model=DocumentResponse)
async def retry_document_route(
    document_id: UUID,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    document = await retry_document(db, user_id, document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return DocumentResponse.model_validate(document)


@router.delete("/delete/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id, Document.deleted_at.is_(None))
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    from datetime import datetime
    document.deleted_at = datetime.utcnow()
    await db.commit()
