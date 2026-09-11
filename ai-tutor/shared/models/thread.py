"""数据模型 - Thread & Run"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import relationship

from .user import Base


class Thread(Base):
    """Thread 模型 - Agent 对话线程"""

    __tablename__ = "threads"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    agent_type = Column(String(50), nullable=False)  # feynman, quiz, review, knowledge, progress
    title = Column(String(200), nullable=True)
    status = Column(String(20), default="active", index=True)  # active, completed, paused
    state = Column(JSON, default=dict)
    metadata_ = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    runs = relationship("Run", back_populates="thread", cascade="all, delete-orphan")


class Run(Base):
    """Run 模型 - Agent 执行记录"""

    __tablename__ = "runs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    thread_id = Column(PG_UUID(as_uuid=True), ForeignKey("threads.id"), nullable=False, index=True)
    agent_type = Column(String(50), nullable=False)
    status = Column(
        String(20),
        default="pending",
        index=True,
    )  # pending, running, completed, failed, waiting_hitl
    input = Column(JSON, nullable=False)
    output = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    hitl_required = Column(Boolean, default=False)
    hitl_action = Column(String(100), nullable=True)
    hitl_options = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    thread = relationship("Thread", back_populates="runs")


# Pydantic Schemas
class ThreadCreate(BaseModel):
    """创建 Thread 请求"""

    agent_type: str


class ThreadResponse(BaseModel):
    """Thread 响应"""

    id: UUID
    agent_type: str
    title: str | None = None
    status: str
    state: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class RunCreate(BaseModel):
    """创建 Run 请求"""

    agent_type: str
    action: str
    input: dict | str = {}


class RunResponse(BaseModel):
    """Run 响应"""

    id: UUID
    thread_id: UUID
    agent_type: str
    status: str
    input: dict
    output: dict | None = None
    hitl_required: bool = False
    hitl_action: str | None = None
    hitl_options: dict | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class HITLResume(BaseModel):
    """HITL 恢复请求"""

    action: str
    input: dict


# SSE Events
class SSEEvent(BaseModel):
    """SSE 事件"""

    event: str
    data: dict
    run_id: UUID | None = None
    timestamp: datetime = datetime.utcnow()
