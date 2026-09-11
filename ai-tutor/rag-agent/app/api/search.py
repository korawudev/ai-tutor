from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import SearchResponse
from shared.database import get_db
from shared.utils import decode_access_token
from ..services import search_knowledge

router = APIRouter(prefix="/api/rag", tags=["rag"])


async def get_user_id_dependency(authorization: str = Header(None)) -> UUID:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    token = authorization.split(" ", 1)[1]
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return UUID(payload["sub"])


@router.post("/query", response_model=SearchResponse)
async def query_knowledge(
    query: str,
    rewrite: bool = True,
    top_k: int = 5,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    response = await search_knowledge(db, query, user_id, top_k=top_k, rewrite=rewrite)
    return response


@router.post("/rewrite")
async def rewrite_search_query(
    query: str,
    num_variants: int = 4,
    user_id: UUID = Depends(get_user_id_dependency)
):
    from ..tools import rewrite_query
    result = await rewrite_query(query, num_variants)
    return {"original": result.original, "variants": result.variants}
