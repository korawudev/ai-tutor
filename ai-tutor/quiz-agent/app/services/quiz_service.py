"""测验服务"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Quiz

from ..tools import add_wrong_question, generate_questions, get_wrong_questions, grade_answer


async def generate_quiz(
    db: AsyncSession,
    user_id: UUID,
    scope: str,
    topic: str | None = None,
    time_range: dict | None = None,
    question_count: int = 5,
    difficulty: str = "medium",
) -> Quiz:
    """
    生成测验

    Args:
        db: 数据库会话
        user_id: 用户 ID
        scope: 范围 (topic, time_range, wrong_review)
        topic: 主题
        time_range: 时间范围
        question_count: 题目数量
        difficulty: 难度

    Returns:
        Quiz
    """
    # 获取知识上下文
    knowledge_context = await _get_knowledge_context(db, user_id, scope, topic, time_range)

    # 生成题目
    questions = await generate_questions(
        topic=topic or "综合知识",
        knowledge_context=knowledge_context,
        question_count=question_count,
        difficulty=difficulty,
        _scope=scope,
    )

    # 创建测验
    quiz = Quiz(
        user_id=user_id,
        scope=scope,
        topic=topic,
        time_range=time_range,
        difficulty=difficulty,
        questions=[q.__dict__ for q in questions],
        total_questions=len(questions),
        status="pending",
    )

    db.add(quiz)
    await db.commit()
    await db.refresh(quiz)

    return quiz


async def submit_answer(
    db: AsyncSession,
    quiz_id: UUID,
    user_id: UUID,
    answers: dict[str, str],
) -> dict[str, Any]:
    """
    提交测验答案

    Args:
        db: 数据库会话
        quiz_id: 测验 ID
        user_id: 用户 ID
        answers: 答案 {question_id: answer}

    Returns:
        测验结果
    """
    # 获取测验
    result = await db.execute(
        select(Quiz).where(Quiz.id == quiz_id, Quiz.user_id == user_id),
    )
    quiz = result.scalar_one_or_none()

    if not quiz:
        raise ValueError("Quiz not found")

    # 评分
    total_score = 0
    max_score = 0
    correct_count = 0
    results = []
    wrong_questions = []

    for question in quiz.questions:
        q_id = question.get("id")
        user_answer = answers.get(q_id, "")

        grade_result = await grade_answer(question, user_answer, question.get("type"))

        total_score += grade_result.score
        max_score += grade_result.max_score

        if grade_result.correct:
            correct_count += 1

        results.append(
            {
                "question_id": q_id,
                "correct": grade_result.correct,
                "score": grade_result.score,
                "max_score": grade_result.max_score,
                "feedback": grade_result.feedback,
                "user_answer": user_answer,
                "correct_answer": question.get("answer"),
            },
        )

        # 记录错题
        if not grade_result.correct:
            wrong_question = await add_wrong_question(
                db,
                user_id,
                quiz_id,
                question,
                user_answer,
                question.get("answer", ""),
                question.get("explanation", ""),
                error_type=question.get("type"),
            )
            wrong_questions.append(wrong_question)

    # 更新测验
    quiz.answers = answers
    quiz.score = (total_score / max_score * 100) if max_score > 0 else 0
    quiz.correct_count = correct_count
    quiz.status = "completed"
    quiz.completed_at = datetime.utcnow()

    await db.commit()

    # 计算掌握度变化
    mastery_change = _calculate_mastery_change(correct_count, len(quiz.questions))

    return {
        "quiz_id": str(quiz.id),
        "score": quiz.score,
        "total_questions": quiz.total_questions,
        "correct_count": correct_count,
        "results": results,
        "wrong_questions": [
            {
                "id": str(wq.id),
                "question": wq.question,
                "user_answer": wq.user_answer,
                "correct_answer": wq.correct_answer,
            }
            for wq in wrong_questions
        ],
        "mastery_change": mastery_change,
        "time_spent_seconds": 0,
    }


async def _get_knowledge_context(
    db: AsyncSession,
    user_id: UUID,
    scope: str,
    topic: str | None,
    time_range: dict | None,
) -> str:
    """获取知识上下文"""
    if scope == "topic" and topic:
        # 检索相关知识块
        query = """
            SELECT c.content
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.user_id = :user_id
              AND d.deleted_at IS NULL
              AND c.content ILIKE :keyword
            LIMIT 10
        """
        result = await db.execute(query, {"user_id": user_id, "keyword": f"%{topic}%"})
        rows = result.fetchall()
        return "\n\n".join([row.content for row in rows])

    if scope == "time_range" and time_range:
        # 获取时间范围内的知识
        start = time_range.get("start")
        end = time_range.get("end")
        query = """
            SELECT c.content
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.user_id = :user_id
              AND d.deleted_at IS NULL
              AND d.created_at >= :start
              AND d.created_at <= :end
            LIMIT 20
        """
        result = await db.execute(query, {"user_id": user_id, "start": start, "end": end})
        rows = result.fetchall()
        return "\n\n".join([row.content for row in rows])

    if scope == "wrong_review":
        # 获取错题相关的知识
        wrong_questions = await get_wrong_questions(db, user_id, mastered=False, limit=10)
        if wrong_questions:
            return "\n\n".join(
                [
                    f"题目: {wq.question.get('question', '')}\n正确答案: {wq.correct_answer}"
                    for wq in wrong_questions
                ],
            )

    return "请基于通用编程知识生成测验。"


def _calculate_mastery_change(correct_count: int, total_count: int) -> float:
    """计算掌握度变化"""
    if total_count == 0:
        return 0.0

    accuracy = correct_count / total_count

    if accuracy >= 0.9:
        return 10.0
    if accuracy >= 0.7:
        return 5.0
    if accuracy >= 0.5:
        return 0.0
    if accuracy >= 0.3:
        return -5.0
    return -10.0
