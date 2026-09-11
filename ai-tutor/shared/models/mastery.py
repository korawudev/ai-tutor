"""数据模型 - Mastery & Learning Stats"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import Column, String, DateTime, JSON, Integer, ForeignKey, Numeric, Date
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from .user import Base


class MasteryRecord(Base):
    """掌握度记录"""
    __tablename__ = "mastery_records"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    chunk_id = Column(PG_UUID(as_uuid=True), ForeignKey("chunks.id"), nullable=False)
    topic = Column(String(500), nullable=True)
    mastery_score = Column(Numeric(5, 2), default=0.0)
    quiz_accuracy = Column(Numeric(5, 2), default=0.0)
    feynman_score = Column(Numeric(5, 2), default=0.0)
    review_score = Column(Numeric(5, 2), nullable=True)
    review_count = Column(Integer, default=0)
    last_quiz_at = Column(DateTime(timezone=True), nullable=True)
    last_feynman_at = Column(DateTime(timezone=True), nullable=True)
    last_review_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


class LearningStats(Base):
    """学习统计"""
    __tablename__ = "learning_stats"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    date = Column(Date, nullable=False)
    total_time_seconds = Column(Integer, default=0)
    documents_read = Column(Integer, default=0)
    quizzes_taken = Column(Integer, default=0)
    quiz_avg_score = Column(Numeric(5, 2), nullable=True)
    feynman_sessions = Column(Integer, default=0)
    feynman_avg_score = Column(Numeric(5, 2), nullable=True)
    reviews_completed = Column(Integer, default=0)
    new_concepts_learned = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
