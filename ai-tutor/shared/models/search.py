from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    score: float
    topic: Optional[str] = None
    metadata: Optional[dict] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    rewritten_query: Optional[str] = None
    total_results: int
