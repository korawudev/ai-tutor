"""费曼学习法评估器"""

from dataclasses import dataclass
from typing import Any

from shared.llm import llm_router


@dataclass
class EvaluationResult:
    """评估结果"""

    score: int  # 0-100
    dimensions: dict[str, int]  # accuracy, clarity, completeness
    gaps: list[str]
    follow_up: str
    feedback: str


class FeynmanEvaluator:
    """
    费曼学习法评估器

    ⚠️ 独立方法，后期可修改评估标准
    """

    def __init__(self):
        # 评估权重
        self.weights = {
            "accuracy": 0.4,  # 概念准确性
            "clarity": 0.3,  # 逻辑连贯性
            "completeness": 0.3,  # 完整性
        }

    async def evaluate_explanation(
        self,
        user_explanation: str,
        reference_knowledge: str,
        topic: str,
        conversation_history: list[dict] | None = None,
    ) -> EvaluationResult:
        """
        评估用户解释

        Args:
            user_explanation: 用户解释
            reference_knowledge: 参考知识
            topic: 主题
            conversation_history: 对话历史

        Returns:
            EvaluationResult
        """
        prompt = f"""你是一个专业的学习评估专家。请评估用户对 "{topic}" 的解释。

参考知识:
{reference_knowledge}

用户解释:
{user_explanation}

{"对话历史: " + str(conversation_history) if conversation_history else ""}

请从以下维度评估（每项满分如下）:
1. 概念准确性 (满分40): 关键概念是否正确
2. 逻辑连贯性 (满分30): 解释是否清晰有条理
3. 完整性 (满分30): 是否覆盖核心要点

请返回 JSON 格式:
{{
    "accuracy": 分数,
    "clarity": 分数,
    "completeness": 分数,
    "gaps": ["遗漏点1", "遗漏点2"],
    "follow_up": "引导追问的问题",
    "feedback": "整体反馈"
}}"""

        try:
            response = await llm_router.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
            )

            content = response["content"]

            # 解析 JSON
            import json
            import re

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())

                accuracy = min(data.get("accuracy", 0), 40)
                clarity = min(data.get("clarity", 0), 30)
                completeness = min(data.get("completeness", 0), 30)

                total_score = accuracy + clarity + completeness

                return EvaluationResult(
                    score=total_score,
                    dimensions={
                        "accuracy": accuracy,
                        "clarity": clarity,
                        "completeness": completeness,
                    },
                    gaps=data.get("gaps", []),
                    follow_up=data.get("follow_up", "能再详细解释一下吗？"),
                    feedback=data.get("feedback", ""),
                )

        except Exception as e:
            print(f"Evaluation failed: {e}")

        # 失败时返回默认评估
        return EvaluationResult(
            score=50,
            dimensions={
                "accuracy": 20,
                "clarity": 15,
                "completeness": 15,
            },
            gaps=["无法自动评估，请手动检查"],
            follow_up="能再详细解释一下吗？",
            feedback="评估过程中出现错误，请手动评估。",
        )

    async def generate_final_evaluation(
        self,
        conversation_history: list[dict],
        reference_knowledge: str,
        topic: str,
    ) -> dict[str, Any]:
        """
        生成最终评价

        Args:
            conversation_history: 完整对话历史
            reference_knowledge: 参考知识
            topic: 主题

        Returns:
            最终评价
        """
        prompt = f"""基于以下对话历史，生成对用户学习 "{topic}" 的最终评价。

参考知识:
{reference_knowledge}

对话历史:
{conversation_history}

请评价:
1. 用户理解正确的部分
2. 用户理解错误的部分
3. 用户记忆模糊的部分

请返回 JSON 格式:
{{
    "final_score": 总分(0-100),
    "understood_well": ["理解正确的概念1", "概念2"],
    "understood_wrong": [
        {{"concept": "错误概念", "user_thought": "用户理解", "correct": "正确理解"}}
    ],
    "unclear": [
        {{"concept": "模糊概念", "importance": "high/medium/low"}}
    ]
}}"""

        try:
            response = await llm_router.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500,
            )

            content = response["content"]

            import json
            import re

            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())

        except Exception as e:
            print(f"Final evaluation failed: {e}")

        # 失败时返回默认评价
        return {
            "final_score": 50,
            "understood_well": [],
            "understood_wrong": [],
            "unclear": [{"concept": topic, "importance": "high"}],
        }


# 全局实例
feynman_evaluator = FeynmanEvaluator()
