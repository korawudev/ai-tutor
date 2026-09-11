"""Unit tests for review-agent tools."""
import pytest
from datetime import datetime, timedelta


class TestSpacedRepetition:
    def test_initial_interval(self, review_modules):
        interval, ef = review_modules.get_initial_interval()
        assert interval == 1.0
        assert ef == 2.5

    def test_easy_result(self, review_modules):
        r = review_modules.calculate_next_review("easy", 1.0, 2.5, 50.0)
        assert r.new_interval > 1.0
        assert r.ease_factor > 2.5
        assert r.mastery_score == 65.0
        assert r.status == "active"

    def test_good_result(self, review_modules):
        r = review_modules.calculate_next_review("good", 1.0, 2.5, 50.0)
        assert r.new_interval == 2.5
        assert r.ease_factor == 2.6
        assert r.mastery_score == 60.0

    def test_hard_result(self, review_modules):
        r = review_modules.calculate_next_review("hard", 2.0, 2.5, 50.0)
        assert r.new_interval < 2.0 * 2.5
        assert r.ease_factor == 2.4
        assert r.mastery_score == 45.0

    def test_forgot_result(self, review_modules):
        r = review_modules.calculate_next_review("forgot", 5.0, 2.5, 50.0)
        assert r.new_interval == 1.0
        assert r.ease_factor == 2.3
        assert r.mastery_score == 35.0

    def test_mastery_ceiling(self, review_modules):
        r = review_modules.calculate_next_review("easy", 1.0, 2.5, 95.0)
        assert r.mastery_score == 100.0

    def test_mastery_floor(self, review_modules):
        r = review_modules.calculate_next_review("forgot", 1.0, 2.5, 5.0)
        assert r.mastery_score == 0.0

    def test_ease_factor_ceiling(self, review_modules):
        r = review_modules.calculate_next_review("easy", 1.0, 2.95, 50.0)
        assert r.ease_factor == 3.0

    def test_ease_factor_floor(self, review_modules):
        r = review_modules.calculate_next_review("forgot", 1.0, 1.35, 50.0)
        assert r.ease_factor == 1.3

    def test_mastered_status(self, review_modules):
        r = review_modules.calculate_next_review("easy", 1.0, 2.5, 85.0)
        assert r.status == "mastered"

    def test_active_status(self, review_modules):
        r = review_modules.calculate_next_review("good", 1.0, 2.5, 50.0)
        assert r.status == "active"


class TestMasteryScore:
    def test_perfect_scores(self, review_modules):
        score = review_modules.calculate_mastery_score(100, 100, 10, 0)
        assert 85 <= score <= 100

    def test_zero_scores(self, review_modules):
        score = review_modules.calculate_mastery_score(0, 0, 0, 30)
        assert score >= 0

    def test_recency_decay(self, review_modules):
        score_recent = review_modules.calculate_mastery_score(80, 80, 5, 1)
        score_old = review_modules.calculate_mastery_score(80, 80, 5, 7)
        assert score_recent > score_old

    def test_review_count_boost(self, review_modules):
        score_high = review_modules.calculate_mastery_score(80, 80, 10, 0)
        score_low = review_modules.calculate_mastery_score(80, 80, 0, 0)
        assert score_high > score_low

    def test_clamped_0_100(self, review_modules):
        score = review_modules.calculate_mastery_score(100, 100, 100, 0)
        assert 0 <= score <= 100
