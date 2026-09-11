"""自动评分"""
from typing import Dict, Any, Optional
from dataclasses import dataclass

from shared.llm import llm_router


@dataclass
class GradeResult:
    """评分结果"""
    score: int
    max_score: int
    correct: bool
    feedback: str
    key_points: list = None
    
    def __post_init__(self):
        if self.key_points is None:
            self.key_points = []


async def grade_answer(
    question: Dict[str, Any],
    user_answer: str,
    question_type: str = "short_answer"
) -> GradeResult:
    """
    评分
    
    Args:
        question: 题目信息
        user_answer: 用户答案
        question_type: 题目类型
    
    Returns:
        GradeResult
    """
    if question_type == "choice":
        # 选择题：精确匹配
        correct_answer = question.get("answer", "")
        is_correct = user_answer.strip().upper() == correct_answer.strip().upper()
        
        return GradeResult(
            score=question.get("points", 20) if is_correct else 0,
            max_score=question.get("points", 20),
            correct=is_correct,
            feedback="回答正确！" if is_correct else f"正确答案是 {correct_answer}",
            key_points=[]
        )
    
    # 简答题和概念辨析题：LLM 评分
    prompt = f"""你是一个专业的编程教育评分专家。请评估用户的答案。

题目: {question.get("question", "")}
题目类型: {question_type}
参考答案: {question.get("answer", "")}
解析: {question.get("explanation", "")}

用户答案:
{user_answer}

请从以下方面评估:
1. 关键点覆盖程度
2. 概念准确性
3. 表达清晰度

满分 {question.get("points", 20)} 分。

请返回 JSON 格式:
{{
    "score": 分数,
    "correct": true/false,
    "feedback": "详细反馈",
    "key_points": ["关键点1", "关键点2"]
}}"""

    try:
        response = await llm_router.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )
        
        content = response["content"]
        
        import json
        import re
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            
            max_score = question.get("points", 20)
            score = min(data.get("score", 0), max_score)
            
            return GradeResult(
                score=score,
                max_score=max_score,
                correct=data.get("correct", score >= max_score * 0.6),
                feedback=data.get("feedback", ""),
                key_points=data.get("key_points", [])
            )
    
    except Exception as e:
        print(f"Grading failed: {e}")
    
    # 失败时返回默认评分
    max_score = question.get("points", 20)
    return GradeResult(
        score=max_score // 2,
        max_score=max_score,
        correct=False,
        feedback="评分过程中出现错误，请手动评估。",
        key_points=[]
    )
