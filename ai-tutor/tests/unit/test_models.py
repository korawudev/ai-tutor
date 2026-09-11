"""Unit tests for shared models."""

from datetime import datetime
from uuid import uuid4

from shared.models.document import (
    DocumentCreate,
    DocumentImport,
    DocumentResponse,
    DuplicateDetected,
    ImportResult,
)
from shared.models.quiz import QuizGenerate, QuizResponse, QuizResult, QuizSubmit
from shared.models.review import ReviewListResponse, ReviewResult, ReviewSubmit
from shared.models.user import Token, UserCreate, UserLogin, UserResponse


class TestDocumentModels:
    def test_document_create(self):
        doc = DocumentCreate(title="Test", source_type="url", source_url="https://example.com")
        assert doc.title == "Test"
        assert doc.source_type == "url"

    def test_document_import(self):
        imp = DocumentImport(sources=[{"type": "url", "value": "https://x.com"}], tags=["t"])
        assert len(imp.sources) == 1
        assert imp.on_duplicate == "ask"

    def test_document_response(self):
        resp = DocumentResponse(
            id=uuid4(),
            title="T",
            source_type="url",
            status="completed",
            tags=[],
            chunk_count=0,
            created_at=datetime.utcnow(),
        )
        assert resp.status == "completed"

    def test_duplicate_detected(self):
        dup = DuplicateDetected(
            source_id="s1",
            existing_doc_id=uuid4(),
            existing_title="Existing",
            message="Already exists",
        )
        assert dup.message == "Already exists"

    def test_import_result(self):
        result = ImportResult(
            batch_id=uuid4(),
            total=1,
            completed=1,
            failed=0,
            skipped=0,
            documents=[],
            duplicates=[],
        )
        assert result.completed == 1


class TestQuizModels:
    def test_quiz_generate(self):
        qg = QuizGenerate(scope="topic", topic="Python", question_count=5)
        assert qg.difficulty == "medium"

    def test_quiz_submit(self):
        qs = QuizSubmit(quiz_id=uuid4(), answers={"q1": "A"})
        assert "q1" in qs.answers

    def test_quiz_response(self):
        qr = QuizResponse(
            id=uuid4(),
            scope="topic",
            questions=[],
            total_questions=0,
            status="pending",
            created_at=datetime.utcnow(),
        )
        assert qr.status == "pending"

    def test_quiz_result(self):
        qr = QuizResult(
            quiz_id=uuid4(),
            score=80.0,
            total_questions=5,
            correct_count=4,
            results=[],
            wrong_questions=[],
            mastery_change=5.0,
            time_spent_seconds=0,
        )
        assert qr.score == 80.0


class TestReviewModels:
    def test_review_submit(self):
        rs = ReviewSubmit(schedule_id=uuid4(), result="good")
        assert rs.result == "good"

    def test_review_result(self):
        rr = ReviewResult(
            schedule_id=uuid4(),
            old_interval=1.0,
            new_interval=2.5,
            ease_factor=2.5,
            mastery_score=60.0,
            next_review=datetime.utcnow(),
            status="active",
        )
        assert rr.status == "active"

    def test_review_list_response(self):
        rlr = ReviewListResponse(pending_count=0, overdue_count=0, items=[])
        assert rlr.pending_count == 0


class TestUserModels:
    def test_user_create(self):
        uc = UserCreate(email="a@b.com", username="u", password="p123")
        assert uc.email == "a@b.com"

    def test_user_login(self):
        ul = UserLogin(email="a@b.com", password="p123")
        assert ul.email == "a@b.com"

    def test_token_model(self):
        t = Token(
            access_token="abc",
            expires_in=3600,
            user=UserResponse(
                id=uuid4(),
                email="a@b.com",
                username="u",
                created_at=datetime.utcnow(),
            ),
        )
        assert t.expires_in == 3600
