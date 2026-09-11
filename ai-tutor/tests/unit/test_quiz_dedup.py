"""Unit tests for quiz dedup helpers."""
from gateway.app.api.quiz import _dedup_filter


class TestDedupFilter:
    def test_exact_duplicate_removed(self):
        seen = ["在Python中如何定义一个函数"]
        questions = [
            {"question": "在Python中如何定义一个函数", "topic": "T"},
            {"question": "Python 列表支持哪些操作", "topic": "T"},
        ]
        result = _dedup_filter(questions, list(seen))
        assert len(result) == 1
        assert result[0]["question"] == "Python 列表支持哪些操作"

    def test_empty_seen_keeps_all(self):
        questions = [{"question": "A题"}, {"question": "B题"}]
        assert _dedup_filter(questions, []) == questions

    def test_blank_question_kept(self):
        questions = [{"question": "  ", "topic": "T"}, {"question": "新题", "topic": "T"}]
        result = _dedup_filter(questions, ["正常题"])
        assert len(result) == 2
        assert result[0]["question"] == "  "
