from pydantic import BaseModel


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    content: str
    score: float
    topic: str | None = None
    metadata: dict | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    rewritten_query: str | None = None
    total_results: int
