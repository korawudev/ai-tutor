"""测验题目生成器"""
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from shared.llm import llm_router


@dataclass
class GeneratedQuestion:
    """生成的题目"""
    id: str
    type: str  # choice, short_answer, concept_analysis
    question: str
    options: Optional[Dict[str, str]] = None
    answer: Optional[str] = None
    explanation: Optional[str] = None
    topic: str = ""
    points: int = 20


async def generate_questions(
    topic: str,
    knowledge_context: str,
    question_count: int = 5,
    difficulty: str = "medium",
    scope: str = "topic"
) -> List[GeneratedQuestion]:
    """
    生成测验题目
    
    Args:
        topic: 主题
        knowledge_context: 知识上下文
        question_count: 题目数量
        difficulty: 难度 (easy, medium, hard)
        scope: 范围 (topic, time_range, wrong_review)
    
    Returns:
        题目列表
    """
    prompt = f"""你是一个专业的编程教育专家。请基于以下知识生成 {question_count} 道测验题目。

知识内容:
{knowledge_context}

要求:
1. 题目类型混合:
   - {question_count // 2} 道选择题 (每题 20 分)
   - {question_count // 3} 道简答题 (每题 20 分)
   - 剩余为概念辨析题 (每题 20 分)

2. 难度: {difficulty}
   - easy: 基础概念
   - medium: 理解应用
   - hard: 深入分析

3. 每道题必须包含:
   - 题目 ID (q1, q2, ...)
   - 题目类型
   - 题目内容
   - 如果是选择题: 4 个选项 (A, B, C, D)
   - 正确答案
   - 解析

请返回 JSON 格式:
{{
    "questions": [
        {{
            "id": "q1",
            "type": "choice",
            "question": "题目内容",
            "options": {{"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"}},
            "answer": "A",
            "explanation": "解析",
            "topic": "知识点",
            "points": 20
        }},
        {{
            "id": "q2",
            "type": "short_answer",
            "question": "题目内容",
            "answer": "参考答案",
            "explanation": "解析",
            "topic": "知识点",
            "points": 20
        }},
        {{
            "id": "q3",
            "type": "concept_analysis",
            "question": "请解释A和B的区别",
            "answer": "参考答案",
            "explanation": "解析",
            "topic": "知识点",
            "points": 20
        }}
    ]
}}"""

    try:
        response = await llm_router.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=2000
        )
        
        content = response["content"]
        
        import json
        import re
        
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            questions_data = data.get("questions", [])
            
            questions = []
            for q in questions_data:
                questions.append(GeneratedQuestion(
                    id=q.get("id", f"q{len(questions) + 1}"),
                    type=q.get("type", "short_answer"),
                    question=q.get("question", ""),
                    options=q.get("options"),
                    answer=q.get("answer"),
                    explanation=q.get("explanation"),
                    topic=q.get("topic", topic),
                    points=q.get("points", 20)
                ))
            
            return questions[:question_count]
    
    except Exception as e:
        print(f"Question generation failed: {e}")
    
    # 失败时返回默认题目
    return [
        GeneratedQuestion(
            id="q1",
            type="choice",
            question=f"关于 {topic}，以下哪个描述是正确的？",
            options={"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
            answer="A",
            explanation="请选择正确答案。",
            topic=topic,
            points=20
        )
    ]
