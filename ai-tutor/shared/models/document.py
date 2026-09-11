"""数据模型 - Document & Chunk"""

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from pydantic import BaseModel
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from .user import Base


class Document(Base):
    """文档模型"""

    __tablename__ = "documents"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    source_type = Column(String(20), nullable=False)  # url, file, manual
    source_url = Column(String(2000), nullable=True)
    file_path = Column(String(500), nullable=True)
    file_hash = Column(String(64), nullable=True, index=True)
    content = Column(Text, nullable=True)
    raw_html = Column(Text, nullable=True)
    scrape_method = Column(String(20), default="trafilatura")
    status = Column(
        String(20),
        default="pending",
        index=True,
    )  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    tags = Column(JSON, default=list)
    metadata_ = Column("metadata", JSON, default=dict)
    chunk_count = Column(Integer, default=0)
    batch_id = Column(PG_UUID(as_uuid=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")


class Chunk(Base):
    """知识块模型"""

    __tablename__ = "chunks"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id = Column(
        PG_UUID(as_uuid=True),
        ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1024), nullable=True)
    metadata_ = Column("metadata", JSON, default=dict)
    chunk_index = Column(Integer, nullable=False)
    token_count = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    document = relationship("Document", back_populates="chunks")


class ImportBatch(Base):
    """批量导入记录"""

    __tablename__ = "import_batches"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    total_count = Column(Integer, nullable=False)
    completed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    status = Column(String(20), default="processing")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)


# Pydantic Schemas
class DocumentCreate(BaseModel):
    """创建文档请求"""

    title: str
    source_type: str  # url, file, manual
    source_url: str | None = None
    file_path: str | None = None
    content: str | None = None
    tags: list[str] = []


class DocumentImport(BaseModel):
    """批量导入请求"""

    sources: list[dict]  # [{"type": "url", "value": "..."}, ...]
    tags: list[str] = []
    on_duplicate: str = "ask"  # ask, skip, overwrite


class DocumentResponse(BaseModel):
    """文档响应"""

    id: UUID
    title: str
    source_type: str
    source_url: str | None = None
    status: str
    tags: list[str]
    chunk_count: int
    error_message: str | None = None
    created_at: datetime
    processed_at: datetime | None = None

    model_config = {"from_attributes": True}


class DuplicateDetected(BaseModel):
    """重复文档检测"""

    source_id: str
    existing_doc_id: UUID
    existing_title: str
    message: str


class ImportResult(BaseModel):
    """导入结果"""

    batch_id: UUID
    total: int
    completed: int
    failed: int
    skipped: int
    documents: list[DocumentResponse]
    duplicates: list[DuplicateDetected] = []
