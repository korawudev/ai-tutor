"""Unit tests for review-agent tools."""


class TestSpacedRepetition:
    def test_initial_interval(self, review_modules):
        interval, ef = review_modules.get_initial_interval()
        assert interval == 1.0
        assert ef == 2.5

    def test_mastered_first_time(self, review_modules):
        r = review_modules.calculate_next_review("mastered", 1.0, 2.5, 50.0)
        assert r.new_interval == 1.0  # streak 0 → 固定间隔 1 天
        assert r.ease_factor == 2.65  # 2.5 + 0.15
        assert r.mastery_score == 65.0  # 50 + 15
        assert r.correct_streak == 1
        assert r.need_session_retry is False
        assert r.status == "active"

    def test_mastered_second_time(self, review_modules):
        r = review_modules.calculate_next_review("mastered", 1.0, 2.5, 50.0, correct_streak=1)
        assert r.new_interval == 6.0  # streak 1 → 固定间隔 6 天
        assert r.correct_streak == 2
        assert r.status == "active"

    def test_mastered_third_time_uses_ef(self, review_modules):
        r = review_modules.calculate_next_review("mastered", 5.0, 2.5, 50.0, correct_streak=2)
        assert r.new_interval == 12.5  # streak ≥2 → current_interval * ease_factor (5.0 * 2.5)
        assert r.correct_streak == 3
        assert r.status == "mastered"  # 连续 3 次答对毕业

    def test_vague_result(self, review_modules):
        r = review_modules.calculate_next_review("vague", 2.0, 2.5, 50.0)
        assert r.new_interval == 1.0  # max(1.0, 2.0 * 0.5)
        assert r.ease_factor == 2.4  # 2.5 - 0.1
        assert r.mastery_score == 45.0  # 50 - 5
        assert r.correct_streak == 0
        assert r.need_session_retry is True
        assert r.retry_reason == "vague"
        assert r.status == "active"

    def test_forgot_result(self, review_modules):
        r = review_modules.calculate_next_review("forgotten", 5.0, 2.5, 50.0)
        assert r.new_interval == 1.0  # 重置到最小间隔
        assert r.ease_factor == 2.3  # 2.5 - 0.2
        assert r.mastery_score == 35.0  # 50 - 15
        assert r.correct_streak == 0
        assert r.need_session_retry is True
        assert r.retry_reason == "forgotten"
        assert r.status == "active"

    def test_mastery_ceiling(self, review_modules):
        r = review_modules.calculate_next_review("mastered", 1.0, 2.5, 95.0)
        assert r.mastery_score == 100.0

    def test_mastery_floor(self, review_modules):
        r = review_modules.calculate_next_review("forgotten", 1.0, 2.5, 5.0)
        assert r.mastery_score == 0.0

    def test_ease_factor_ceiling(self, review_modules):
        r = review_modules.calculate_next_review("mastered", 1.0, 2.95, 50.0)
        assert r.ease_factor == 3.0

    def test_ease_factor_floor(self, review_modules):
        r = review_modules.calculate_next_review("forgotten", 1.0, 1.35, 50.0)
        assert r.ease_factor == 1.3

    def test_mastered_status_requires_streak_3(self, review_modules):
        r = review_modules.calculate_next_review("mastered", 1.0, 2.5, 85.0, correct_streak=2)
        assert r.status == "mastered"

    def test_active_status(self, review_modules):
        r = review_modules.calculate_next_review("mastered", 1.0, 2.5, 50.0)
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
