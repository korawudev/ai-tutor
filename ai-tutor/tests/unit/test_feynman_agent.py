"""Unit tests for feynman-agent."""

from unittest.mock import AsyncMock, patch

import pytest


class TestFeynmanStateMachine:
    def test_state_transitions(self, feynman_modules):
        assert feynman_modules.FeynmanState.INIT.value == "init"
        assert feynman_modules.FeynmanState.LISTENING.value == "listening"
        assert feynman_modules.FeynmanState.EVALUATING.value == "evaluating"
        assert feynman_modules.FeynmanState.COMPLETED.value == "completed"


class TestFeynmanEvaluator:
    @pytest.mark.asyncio
    async def test_evaluate_returns_score(self, feynman_modules):
        with patch("app.evaluator.llm_router") as mock_llm:
            mock_llm.chat = AsyncMock(
                return_value={
                    "content": '{"accuracy": 35, "clarity": 25, "completeness": 28, '
                    '"gaps": ["inheritance"], "follow_up": "Tell me more", '
                    '"feedback": "Good explanation"}',
                },
            )
            result = await feynman_modules.evaluate_explanation(
                "A class is...",
                "reference knowledge",
                "Python Classes",
            )
            assert result.score == 88
            assert result.dimensions["accuracy"] == 35

    @pytest.mark.asyncio
    async def test_evaluate_handles_llm_error(self, feynman_modules):
        with patch("app.evaluator.llm_router") as mock_llm:
            mock_llm.chat = AsyncMock(side_effect=Exception("LLM fail"))
            result = await feynman_modules.evaluate_explanation(
                "explain",
                "reference",
                "topic",
            )
            assert result.score == 50
