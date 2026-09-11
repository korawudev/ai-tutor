"""数据模型 - Quiz & WrongQuestion"""
from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import Column, String, DateTime, JSON, Text, Integer, ForeignKey, Numeric, Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from .user import Base


class Quiz(Base):
    """测验模型"""
    __tablename__ = "quizzes"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    thread_id = Column(PG_UUID(as_uuid=True), ForeignKey("threads.id"), nullable=True)
    scope = Column(String(20), nullable=False)  # daily, topic, time_range, wrong_review
    topic = Column(String(500), nullable=True)
    time_range = Column(JSON, nullable=True)
    difficulty = Column(String(20), default="medium")
    questions = Column(JSON, nullable=False)
    answers = Column(JSON, nullable=True)
    score = Column(Numeric(5, 2), nullable=True)
    total_questions = Column(Integer, nullable=False)
    correct_count = Column(Integer, default=0)
    time_spent_seconds = Column(Integer, nullable=True)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)


class WrongQuestion(Base):
    """错题模型"""
    __tablename__ = "wrong_questions"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    quiz_id = Column(PG_UUID(as_uuid=True), ForeignKey("quizzes.id"), nullable=True)
    question = Column(JSON, nullable=False)
    user_answer = Column(Text, nullable=True)
    correct_answer = Column(Text, nullable=True)
    explanation = Column(Text, nullable=True)
    chunk_ids = Column(JSON, nullable=True)
    error_type = Column(String(50), nullable=True)
    review_count = Column(Integer, default=0)
    mastered = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    last_reviewed_at = Column(DateTime(timezone=True), nullable=True)


# Pydantic Schemas
class QuizGenerate(BaseModel):
    """生成测验请求"""
    scope: str  # topic, time_range, wrong_review
    topic: Optional[str] = None
    time_range: Optional[dict] = None
    question_count: int = 5
    difficulty: str = "medium"


class QuizQuestion(BaseModel):
    """测验题目"""
    id: str
    type: str  # choice, short_answer, concept_analysis
    question: str
    options: Optional[dict] = None  # 选择题选项
    topic: str


class QuizResponse(BaseModel):
    """测验响应"""
    id: UUID
    scope: str
    topic: Optional[str] = None
    questions: List[QuizQuestion]
    total_questions: int
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class QuizSubmit(BaseModel):
    """提交测验答案"""
    quiz_id: UUID
    answers: dict  # {question_id: answer}


class SuggestedReview(BaseModel):
    """加入复习计划建议项"""
    wrong_id: UUID
    question: dict
    user_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None


class QuizResult(BaseModel):
    """测验结果"""
    quiz_id: UUID
    score: float
    total_questions: int
    correct_count: int
    results: List[dict]  # 每题结果
    wrong_questions: List[dict]
    suggested_reviews: List[SuggestedReview] = []
    mastery_change: float
    time_spent_seconds: int


class AddToReviewRequest(BaseModel):
    """将错题加入复习计划"""
    wrong_ids: List[UUID]


class AddToReviewResponse(BaseModel):
    """加入复习计划结果"""
    added: int
    skipped: int
    items: List[dict]


class WrongQuestionResponse(BaseModel):
    """错题响应"""
    id: UUID
    question: dict
    user_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    explanation: Optional[str] = None
    review_count: int
    mastered: bool
    in_review: bool = False  # 是否已在复习计划中（source=quiz 的 active 计划）
    created_at: datetime

    model_config = {"from_attributes": True}
