"""Unit tests for shared.utils.similarity."""

from shared.utils.similarity import normalize, similarity


class TestNormalize:
    def test_strips_punctuation_and_whitespace(self):
        assert normalize("  什么是Python?？ ") == "什么是python"

    def test_lowercases(self):
        assert normalize("HTTP 协议") == "http协议"


class TestSimilarity:
    def test_identical_high(self):
        assert similarity("在Python中如何定义一个函数?", "在Python中如何定义一个函数?") >= 0.9

    def test_unrelated_low(self):
        assert similarity("字典是无序的吗", "归并排序的时间复杂度") < 0.3

    def test_empty_returns_zero(self):
        assert similarity("", "abc") == 0.0

    def test_near_duplicate_high(self):
        assert (
            similarity(
                "Python中的列表和元组有什么区别",
                "Python中的列表和元组有什么区别",
            )
            >= 0.9
        )
