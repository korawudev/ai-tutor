"""费曼检测工具"""

from typing import Any

from ..evaluator import EvaluationResult, feynman_evaluator


async def evaluate_explanation(
    user_explanation: str,
    reference_knowledge: str,
    topic: str,
    conversation_history: list[dict] = None,
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
    return await feynman_evaluator.evaluate_explanation(
        user_explanation,
        reference_knowledge,
        topic,
        conversation_history,
    )


async def generate_final_evaluation(
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
    return await feynman_evaluator.generate_final_evaluation(
        conversation_history,
        reference_knowledge,
        topic,
    )


def generate_welcome_message(topic: str, tags: list[str]) -> str:
    """
    生成欢迎消息

    Args:
        topic: 主题
        tags: 标签

    Returns:
        欢迎消息
    """
    tag_text = "、".join(tags) if tags else topic

    return f"""好的，让我们开始费曼学习检测！

你将要解释的主题是：**{topic}**

相关标签：{tag_text}

请用自己的话解释这个概念，假设你在给一个完全不懂编程的人讲解。

我会根据你的解释：
1. 评估你的理解程度
2. 指出可能的知识漏洞
3. 引导你更完整地表达

准备好了吗？请开始你的解释。"""


def generate_guidance_message(
    evaluation: EvaluationResult,
    _topic: str,
) -> str:
    """
    生成引导消息

    Args:
        evaluation: 评估结果
        topic: 主题

    Returns:
        引导消息
    """
    message = f"你的解释得分：{evaluation.score}/100\n\n"

    # 维度得分
    message += "各维度得分：\n"
    message += f"- 概念准确性：{evaluation.dimensions['accuracy']}/40\n"
    message += f"- 逻辑连贯性：{evaluation.dimensions['clarity']}/30\n"
    message += f"- 完整性：{evaluation.dimensions['completeness']}/30\n\n"

    # 反馈
    if evaluation.feedback:
        message += f"反馈：{evaluation.feedback}\n\n"

    # 遗漏点
    if evaluation.gaps:
        message += "你遗漏了以下要点：\n"
        for gap in evaluation.gaps:
            message += f"- {gap}\n"
        message += "\n"

    # 引导问题
    message += f"请继续：{evaluation.follow_up}"

    return message


def generate_final_message(evaluation: dict[str, Any]) -> str:
    """
    生成最终评价消息

    Args:
        evaluation: 最终评价

    Returns:
        最终评价消息
    """
    message = "## 费曼学习检测完成\n\n"
    message += f"**总分：{evaluation.get('final_score', 0)}/100**\n\n"

    # 理解正确的部分
    understood_well = evaluation.get("understood_well", [])
    if understood_well:
        message += "### ✅ 理解正确的部分\n"
        for item in understood_well:
            message += f"- {item}\n"
        message += "\n"

    # 理解错误的部分
    understood_wrong = evaluation.get("understood_wrong", [])
    if understood_wrong:
        message += "### ❌ 理解错误的部分\n"
        for item in understood_wrong:
            message += (
                f"- **{item.get('concept', '')}**：你的理解是「{item.get('user_thought', '')}」，"
                f"正确理解是「{item.get('correct', '')}」\n"
            )
        message += "\n"

    # 记忆模糊的部分
    unclear = evaluation.get("unclear", [])
    if unclear:
        message += "### ⚠️ 记忆模糊的部分\n"
        for item in unclear:
            importance = item.get("importance", "medium")
            emoji = "🔴" if importance == "high" else "🟡" if importance == "medium" else "🟢"
            message += f"- {emoji} {item.get('concept', '')}\n"
        message += "\n"

    message += "---\n\n"
    message += "以上模糊和错误的知识点，你可以选择加入复习计划。"

    return message
