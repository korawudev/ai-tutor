"""Shared test fixtures for AI Tutor test suite."""
import sys
import os
import types
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timedelta

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "shared"))


@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def sample_user(user_id):
    from shared.models import User
    from shared.utils import hash_password
    return User(
        id=user_id,
        email="test@example.com",
        username="testuser",
        hashed_password=hash_password("testpass123"),
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_document(user_id):
    from shared.models import Document
    doc_id = uuid4()
    return Document(
        id=doc_id,
        user_id=user_id,
        title="Test Document",
        source_type="url",
        source_url="https://example.com/doc",
        content="Test content about Python classes",
        status="completed",
        tags=["python", "classes"],
        chunk_count=5,
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_quiz(user_id):
    from shared.models import Quiz
    quiz_id = uuid4()
    return Quiz(
        id=quiz_id,
        user_id=user_id,
        scope="topic",
        topic="Python",
        difficulty="medium",
        questions=[
            {"id": "q1", "type": "choice", "question": "What is a class?", "options": {"A": "A", "B": "B", "C": "C", "D": "D"}, "answer": "A", "points": 20},
            {"id": "q2", "type": "choice", "question": "What is inheritance?", "options": {"A": "A", "B": "B", "C": "C", "D": "D"}, "answer": "B", "points": 20},
        ],
        total_questions=2,
        status="pending",
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_review_schedule(user_id):
    from shared.models import ReviewSchedule
    return ReviewSchedule(
        id=uuid4(),
        user_id=user_id,
        chunk_id=uuid4(),
        topic="Python Classes",
        source="feynman",
        next_review=datetime.utcnow() - timedelta(hours=1),
        interval_days=1.0,
        ease_factor=2.5,
        review_count=0,
        mastery_score=50.0,
        status="active",
        created_at=datetime.utcnow()
    )


@pytest.fixture
def sample_mastery_record(user_id):
    from shared.models import MasteryRecord
    return MasteryRecord(
        id=uuid4(),
        user_id=user_id,
        chunk_id=uuid4(),
        topic="Python Classes",
        mastery_score=75.0,
        quiz_accuracy=80.0,
        feynman_score=70.0,
        review_count=3,
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def valid_token(user_id):
    from shared.utils import create_access_token
    return create_access_token(user_id)


@pytest.fixture
def auth_header(valid_token):
    return {"Authorization": f"Bearer {valid_token}"}
