"""Gateway API - 文档代理 API"""
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Header, UploadFile, status
import httpx

from shared.models import DocumentResponse, DocumentImport, DocumentCreate, ImportResult
from .auth import get_user_id_dependency

router = APIRouter(prefix="/api/documents", tags=["documents"])

KNOWLEDGE_AGENT_URL = "http://knowledge-agent:8001"


def _auth_headers(authorization: str) -> dict:
    return {"Authorization": authorization}


def _proxy_error(resp):
    try:
        detail = resp.json().get("detail", "Knowledge agent error")
    except Exception:
        detail = resp.text or "Knowledge agent error"
    raise HTTPException(status_code=resp.status_code, detail=detail)


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    tags: str = Form(""),
    authorization: str = Header(...),
    user_id: UUID = Depends(get_user_id_dependency),
):
    content = await file.read()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{KNOWLEDGE_AGENT_URL}/api/documents/upload",
            files={"file": (file.filename or "upload", content, file.content_type or "application/octet-stream")},
            data={"tags": tags},
            headers=_auth_headers(authorization),
            timeout=300.0,
        )
        if resp.status_code != 201:
            _proxy_error(resp)
        return resp.json()


@router.post("/import", response_model=ImportResult)
async def import_documents(
    import_data: DocumentImport,
    authorization: str = Header(...),
    user_id: UUID = Depends(get_user_id_dependency),
):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{KNOWLEDGE_AGENT_URL}/api/documents/import",
            json=import_data.model_dump(),
            headers=_auth_headers(authorization),
            timeout=120.0,
        )
        if resp.status_code != 200:
            _proxy_error(resp)
        return resp.json()


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    document_data: DocumentCreate,
    authorization: str = Header(...),
    user_id: UUID = Depends(get_user_id_dependency),
):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{KNOWLEDGE_AGENT_URL}/api/documents",
            json=document_data.model_dump(),
            headers=_auth_headers(authorization),
            timeout=120.0,
        )
        if resp.status_code != 201:
            _proxy_error(resp)
        return resp.json()


@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    status: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    authorization: str = Header(...),
    user_id: UUID = Depends(get_user_id_dependency),
):
    params = {"limit": limit, "offset": offset}
    if status:
        params["status"] = status
    if tag:
        params["tag"] = tag
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{KNOWLEDGE_AGENT_URL}/api/documents",
            params=params,
            headers=_auth_headers(authorization),
            timeout=30.0,
        )
        if resp.status_code != 200:
            _proxy_error(resp)
        return resp.json()


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    authorization: str = Header(...),
    user_id: UUID = Depends(get_user_id_dependency),
):
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{KNOWLEDGE_AGENT_URL}/api/documents/{document_id}",
            headers=_auth_headers(authorization),
            timeout=30.0,
        )
        if resp.status_code != 200:
            _proxy_error(resp)
        return resp.json()


@router.post("/retry/{document_id}", response_model=DocumentResponse)
async def retry_document(
    document_id: UUID,
    authorization: str = Header(...),
    user_id: UUID = Depends(get_user_id_dependency),
):
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{KNOWLEDGE_AGENT_URL}/api/documents/retry/{document_id}",
            headers=_auth_headers(authorization),
            timeout=120.0,
        )
        if resp.status_code != 200:
            _proxy_error(resp)
        return resp.json()


@router.delete("/delete/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    authorization: str = Header(...),
    user_id: UUID = Depends(get_user_id_dependency),
):
    async with httpx.AsyncClient() as client:
        resp = await client.delete(
            f"{KNOWLEDGE_AGENT_URL}/api/documents/delete/{document_id}",
            headers=_auth_headers(authorization),
            timeout=30.0,
        )
        if resp.status_code != 204:
            _proxy_error(resp)
