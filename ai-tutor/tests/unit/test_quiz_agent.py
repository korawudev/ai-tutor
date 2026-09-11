"""Unit tests for quiz-agent tools."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from uuid import uuid4


class TestGenerateQuestions:
    @pytest.mark.asyncio
    async def test_generate_success(self, quiz_modules):
        with patch("app.tools.generate_questions.llm_router") as mock_router:
            mock_router.chat = AsyncMock(return_value={
                "content": '{"questions": [{"id": "q1", "type": "choice", "question": "What is Python?", "options": {"A": "Lang", "B": "Snake", "C": "Tool", "D": "Car"}, "answer": "A", "topic": "Python", "points": 20}]}'
            })
            result = await quiz_modules.generate_questions("Python", "Python is a lang", question_count=1)
            assert len(result) == 1
            assert result[0].id == "q1"

    @pytest.mark.asyncio
    async def test_generate_failure_returns_default(self, quiz_modules):
        with patch("app.tools.generate_questions.llm_router") as mock_router:
            mock_router.chat = AsyncMock(side_effect=Exception("fail"))
            result = await quiz_modules.generate_questions("Python", "ctx", question_count=3)
            assert len(result) >= 1
            assert result[0].type == "choice"

    @pytest.mark.asyncio
    async def test_generate_truncates_to_count(self, quiz_modules):
        with patch("app.tools.generate_questions.llm_router") as mock_router:
            mock_router.chat = AsyncMock(return_value={
                "content": '{"questions": [{"id":"q1","type":"choice","question":"Q1","answer":"A","topic":"t","points":20},{"id":"q2","type":"choice","question":"Q2","answer":"B","topic":"t","points":20},{"id":"q3","type":"choice","question":"Q3","answer":"C","topic":"t","points":20}]}'
            })
            result = await quiz_modules.generate_questions("Python", "ctx", question_count=2)
            assert len(result) == 2


class TestGradeAnswer:
    @pytest.mark.asyncio
    async def test_grade_choice_correct(self, quiz_modules):
        q = {"id": "q1", "type": "choice", "answer": "A", "points": 20}
        result = await quiz_modules.grade_answer(q, "A", "choice")
        assert result.correct is True
        assert result.score == 20

    @pytest.mark.asyncio
    async def test_grade_choice_incorrect(self, quiz_modules):
        q = {"id": "q1", "type": "choice", "answer": "B", "points": 20}
        result = await quiz_modules.grade_answer(q, "A", "choice")
        assert result.correct is False
        assert result.score == 0

    @pytest.mark.asyncio
    async def test_grade_case_insensitive(self, quiz_modules):
        q = {"id": "q1", "type": "choice", "answer": "a", "points": 10}
        result = await quiz_modules.grade_answer(q, "A", "choice")
        assert result.correct is True

    @pytest.mark.asyncio
    async def test_grade_short_answer_keyword_match(self, quiz_modules):
        q = {"id": "q1", "type": "short_answer", "answer": "inheritance", "points": 20}
        with patch("app.tools.grade_answer.llm_router") as mock_llm:
            mock_llm.chat = AsyncMock(return_value={
                "content": '{"score": 18, "correct": true, "feedback": "Good", "key_points": ["inheritance"]}'
            })
            result = await quiz_modules.grade_answer(q, "inheritance is key", "short_answer")
            assert result.correct is True

    @pytest.mark.asyncio
    async def test_grade_no_answer(self, quiz_modules):
        q = {"id": "q1", "type": "choice", "answer": "A", "points": 20}
        result = await quiz_modules.grade_answer(q, "", "choice")
        assert result.correct is False


class TestWrongBook:
    @pytest.mark.asyncio
    async def test_add_wrong_question(self, quiz_modules, mock_db, user_id):
        question = {"id": "q1", "type": "choice", "question": "Q?"}
        wq = await quiz_modules.add_wrong_question(
            mock_db, user_id, uuid4(), question, "A", "B", "explanation"
        )
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_wrong_questions_empty(self, quiz_modules, mock_db, user_id):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result
        result = await quiz_modules.get_wrong_questions(mock_db, user_id)
        assert result == []
