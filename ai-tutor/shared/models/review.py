"""数据模型 - Review"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from enum import Enum

from pydantic import BaseModel
from sqlalchemy import Column, String, DateTime, JSON, Text, ForeignKey, Numeric, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from .user import Base


class NormalReviewAnswer(str, Enum):
    """正式复习作答选项（前端3级映射后端5级）"""
    MASTERED = "mastered"      # 认识 -> quality 5
    VAGUE = "vague"            # 模糊 -> quality 3
    FORGOTTEN = "forgotten"    # 不认识 -> quality 0


class ReviewSchedule(Base):
    """复习调度模型"""
    __tablename__ = "review_schedule"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    chunk_id = Column(PG_UUID(as_uuid=True), ForeignKey("chunks.id"), nullable=True)
    topic = Column(String(500), nullable=True)
    answer = Column(Text, nullable=True)
    source = Column(String(50), default="feynman")  # feynman, quiz, manual
    reason = Column(String(50), nullable=True)  # wrong, unclear, forgotten
    next_review = Column(DateTime(timezone=True), nullable=False, index=True)
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    interval_days = Column(Numeric(10, 2), default=1.0)
    ease_factor = Column(Numeric(5, 2), default=2.5)
    review_count = Column(Integer, default=0)
    mastery_score = Column(Numeric(5, 2), default=0.0)
    correct_streak = Column(Integer, default=0)      # 连续正式答对计数
    last_normal_answer = Column(String(20), nullable=True)  # mastered/vague/forgotten
    is_mastered = Column(Integer, default=0)         # 0/1 标记是否毕业
    status = Column(String(20), default="active", index=True)  # active, paused, mastered
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class ReviewLog(Base):
    """复习日志模型"""
    __tablename__ = "review_logs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    schedule_id = Column(PG_UUID(as_uuid=True), ForeignKey("review_schedule.id"), nullable=False)
    chunk_id = Column(PG_UUID(as_uuid=True), ForeignKey("chunks.id"), nullable=True)
    result = Column(String(20), nullable=False)  # easy, good, hard, forgot / mastered/vague/forgotten
    old_interval = Column(Numeric(10, 2), nullable=True)
    new_interval = Column(Numeric(10, 2), nullable=True)
    ease_factor_change = Column(Numeric(5, 2), nullable=True)
    old_ease_factor = Column(Numeric(5, 2), nullable=True)
    new_ease_factor = Column(Numeric(5, 2), nullable=True)
    old_mastery_score = Column(Numeric(5, 2), nullable=True)
    new_mastery_score = Column(Numeric(5, 2), nullable=True)
    correct_streak = Column(Integer, nullable=True)
    answer_type = Column(String(20), default="normal_review")  # normal_review / session_retry / verification
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class VerificationLog(Base):
    """组后验证日志"""
    __tablename__ = "verification_logs"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    chunk_id = Column(PG_UUID(as_uuid=True), ForeignKey("chunks.id"), nullable=True)
    schedule_id = Column(PG_UUID(as_uuid=True), ForeignKey("review_schedule.id"), nullable=True)
    verification_type = Column(String(20), nullable=False)  # feynman, concept, code, keyword
    user_answer = Column(Text, nullable=True)
    ai_score = Column(Numeric(5, 2), nullable=True)
    passed = Column(Integer, default=0)  # 0/1
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


class ReviewBatchStats(Base):
    """复习组完成统计（基础埋点，v1.0 只写不读）"""
    __tablename__ = "review_batch_stats"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    batch_id = Column(String(64), nullable=False, index=True)
    total_count = Column(Integer, default=0)
    mastered_count = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)
    duration_sec = Column(Integer, default=0)
    avg_response_ms = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)


# Pydantic Schemas
class NormalReviewSubmit(BaseModel):
    """正式复习提交（前端3级映射）"""
    schedule_id: UUID
    answer: NormalReviewAnswer  # mastered / vague / forgotten
    response_time_ms: int = 0


class NormalReviewResponse(BaseModel):
    """正式复习响应"""
    schedule_id: UUID
    chunk_id: Optional[UUID] = None
    next_review_time: datetime
    ease_factor: float
    correct_streak: int
    is_mastered: bool
    need_session_retry: bool = False
    retry_reason: Optional[str] = None  # "vague" | "forgotten"
    mastery_change: Optional[dict] = None  # {"old": 65, "new": 58, "delta": -7}


class SessionRetrySubmit(BaseModel):
    """会话重试提交（仅用于日志记录，可选）"""
    schedule_id: UUID
    chunk_id: UUID
    answer: NormalReviewAnswer
    response_time_ms: int = 0


class VerificationSubmit(BaseModel):
    """验证提交"""
    chunk_id: UUID
    schedule_id: Optional[UUID] = None
    verification_type: str  # feynman, concept, code, keyword
    user_answer: str


class VerificationFailedSubmit(BaseModel):
    """组后验证失败提交（轻降难度，不重置间隔）"""
    chunk_id: Optional[UUID] = None
    schedule_id: Optional[UUID] = None
    response_time_ms: int = 0


class VerificationResponse(BaseModel):
    """验证响应"""
    passed: bool
    ai_score: Optional[float] = None
    feedback: Optional[str] = None
    need_retry: bool = False


class ReviewItem(BaseModel):
    """复习项目"""
    schedule_id: UUID
    chunk_id: Optional[UUID] = None
    topic: str
    answer: Optional[str] = None
    mastery_score: float
    next_review: datetime
    interval_days: float
    review_count: int
    status: str
    source: Optional[str] = None
    reason: Optional[str] = None
    is_mastered: bool = False
    correct_streak: int = 0


class ReviewSubmit(BaseModel):
    """提交复习结果（兼容旧版本）"""
    schedule_id: UUID
    result: str  # easy, good, hard, forgot


class ReviewResult(BaseModel):
    """复习结果"""
    schedule_id: UUID
    old_interval: float
    new_interval: float
    ease_factor: float
    mastery_score: float
    next_review: datetime
    status: str


class ReviewListResponse(BaseModel):
    """复习清单响应"""
    pending_count: int
    overdue_count: int
    items: list[ReviewItem]


class FeynmanVerifySubmit(BaseModel):
    """组后验证费曼评分提交"""
    schedule_id: UUID
    explanation: str


class FeynmanVerifyResponse(BaseModel):
    """组后验证费曼评分响应"""
    schedule_id: UUID
    score: int
    passed: bool
    strengths: list[str] = []
    weaknesses: list[str] = []
    suggestions: list[str] = []
    correct_answer: str = ""


class SessionSnapshot(BaseModel):
    """复习会话快照（前端内存结构原样存储，不做后端校验）"""
    batch_id: str
    batch_index: int
    main_queue: list[ReviewItem]
    retry_queue: list[dict] = []
    verify_queue: list[dict] = []
    current_card: Optional[ReviewItem] = None
    stats: dict = {}


class BatchCompleteSubmit(BaseModel):
    """复习组完成埋点上报"""
    batch_id: str
    total_count: int
    mastered_count: int
    retry_count: int
    duration_sec: int
    avg_response_ms: int
