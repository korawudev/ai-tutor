"""数据模型 - Feynman Session"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import JSON, Column, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from .user import Base


class FeynmanSession(Base):
    """费曼学习会话模型"""

    __tablename__ = "feynman_sessions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    thread_id = Column(PG_UUID(as_uuid=True), ForeignKey("threads.id"), nullable=True)
    topic = Column(String(500), nullable=False)
    knowledge_context = Column(Text, nullable=True)
    state = Column(String(20), default="init")
    rounds = Column(Integer, default=0)
    score = Column(Numeric(5, 2), nullable=True)
    evaluation = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)


# Pydantic Schemas
class FeynmanStart(BaseModel):
    """开始费曼会话请求"""

    topic: str
    knowledge_context: str | None = None


class FeynmanExplain(BaseModel):
    """提交费曼解释"""

    explanation: str


class FeynmanResponse(BaseModel):
    """费曼会话响应"""

    id: UUID
    topic: str
    state: str
    rounds: int
    score: float | None = None
    evaluation: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeynmanEvaluate(BaseModel):
    """费曼评估结果"""

    score: float
    strengths: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[str] = []
    keywords_covered: list[str] = []
    keywords_missing: list[str] = []
