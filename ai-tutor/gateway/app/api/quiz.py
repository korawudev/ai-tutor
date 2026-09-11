"""Gateway API - 测验 API"""
from typing import List
from uuid import UUID
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import (
    Quiz, QuizGenerate, QuizSubmit, QuizResponse, QuizResult,
    WrongQuestion, WrongQuestionResponse,
    SuggestedReview, AddToReviewRequest, AddToReviewResponse,
    ReviewSchedule,
)
from shared.database import get_db
from shared.llm import llm_router
from shared.utils.schedule import compute_next_review_window
from shared.utils.similarity import similarity
from shared.utils.mastery import upsert_mastery, record_daily_stats
from .auth import get_user_id_dependency

router = APIRouter(prefix="/api/quiz", tags=["quiz"])

DEDUP_SAMPLE = 30
DEDUP_THRESHOLD = 0.85


@router.post("/generate", response_model=QuizResponse)
async def generate_quiz(
    data: QuizGenerate,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    # 错题复习: 直接用未掌握错题出题，不走 LLM
    if data.scope == "wrong_review":
        questions_data = await _load_wrong_questions(db, user_id, data.question_count)
    else:
        knowledge_context = await _get_knowledge_context(db, user_id, data.scope, data.topic, data.time_range)
        seen = await _collect_seen_questions(db, user_id, data.scope, data.topic, DEDUP_SAMPLE)
        sample = "\n".join(f"{i}. {t}" for i, t in enumerate(seen, 1))

        base_prompt = f"""基于以下知识生成 {data.question_count} 道测验题目。难度: {data.difficulty}

知识内容:
{knowledge_context[:3000]}

请返回 JSON:
{{
    "questions": [
        {{"id": "q1", "type": "choice", "question": "题目", "options": {{"A": "a", "B": "b", "C": "c", "D": "d"}}, "answer": "A", "explanation": "简要说明为什么答案是A", "topic": "知识点", "points": 20}}
    ]
}}

要求：每道题必须包含 explanation 字段，用一两句话简要解释为什么该答案是正确答案。"""

        dedup_section = f"""
以下是该用户近期已出过的题目,请避免生成相同或含义重复的题目(包括同一知识点换个考法):
{sample}
""" if sample else ""

        import json, re

        def build_prompt(extra=""):
            return base_prompt + dedup_section + extra

        async def generate_once(extra=""):
            response = await llm_router.chat(
                messages=[{"role": "user", "content": build_prompt(extra)}],
                temperature=0.7, max_tokens=2000,
            )
            match = re.search(r'\{.*\}', response["content"], re.DOTALL)
            return json.loads(match.group()).get("questions", []) if match else []

        try:
            questions_data = await generate_once()
        except Exception:
            questions_data = [{"id": "q1", "type": "choice", "question": f"关于 {data.topic or '通用知识'}，以下哪个正确？", "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"}, "answer": "A", "explanation": f"关于 {data.topic or '通用知识'} 的正确表述是选项A，其余选项不符合题干要求。", "topic": data.topic or "", "points": 20}]

        questions_data = _dedup_filter(questions_data[:data.question_count], list(seen))
        if len(questions_data) < data.question_count:
            try:
                more_questions = await generate_once(
                    f"\n当前题目数量不足 {data.question_count},请再补充 {data.question_count - len(questions_data)} 道与上面不同的题目。"
                )
                questions_data += _dedup_filter(more_questions, list(seen))
            except Exception:
                pass

        questions_data = questions_data[:data.question_count]

    quiz = Quiz(
        user_id=user_id, scope=data.scope, topic=data.topic,
        time_range=data.time_range, difficulty=data.difficulty,
        questions=questions_data, total_questions=len(questions_data), status="pending"
    )
    db.add(quiz)
    await db.commit()
    await db.refresh(quiz)

    return QuizResponse(
        id=quiz.id, scope=quiz.scope, topic=quiz.topic,
        questions=questions_data, total_questions=quiz.total_questions,
        status=quiz.status, created_at=quiz.created_at
    )


async def _record_quiz_mastery(db, user_id, quiz, results, quiz_count=1):
    """提交测验后更新掌握度与当日学习统计。

    每个知识点按本场正确率更新 MasteryRecord，同时累加当日 quizzes_taken/reviews_completed。
    """
    per_topic = {}
    for q, r in zip(quiz.questions, results):
        topic = (q.get("topic") or "").strip()
        if not topic:
            continue
        acc = per_topic.setdefault(topic, {"correct": 0, "total": 0})
        acc["total"] += 1
        if r.get("correct"):
            acc["correct"] += 1

    for topic, acc in per_topic.items():
        accuracy = acc["correct"] / acc["total"] * 100
        await upsert_mastery(db, user_id, topic, quiz_accuracy=accuracy)

    await record_daily_stats(
        db, user_id,
        quizzes_taken=quiz_count,
        quiz_avg_score=float(quiz.score) if quiz.score is not None else 0,
        reviews_completed=1 if quiz.scope == "wrong_review" else 0,
        new_concepts_learned=len(per_topic),
    )


@router.post("/submit", response_model=QuizResult)
async def submit_quiz(
    data: QuizSubmit,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Quiz).where(Quiz.id == data.quiz_id, Quiz.user_id == user_id)
    )
    quiz = result.scalar_one_or_none()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    total_score, max_score, correct_count = 0, 0, 0
    results, wrong_questions, suggested_reviews = [], [], []

    # 错题复习模式: 预加载未掌握错题，按题干文本匹配，答对毕业/答错计数，不新增重复错题行
    wrong_by_question = {}
    if quiz.scope == "wrong_review":
        wq_result = await db.execute(
            select(WrongQuestion).where(WrongQuestion.user_id == user_id, WrongQuestion.mastered == False)
        )
        for wq in wq_result.scalars().all():
            wrong_by_question[str(wq.question.get("question", ""))] = wq

    for question in quiz.questions:
        q_id = question.get("id")
        user_answer = data.answers.get(q_id, "")
        correct_answer = question.get("answer", "")
        is_correct = user_answer.strip().upper() == correct_answer.strip().upper()
        pts = question.get("points", 20)
        total_score += pts if is_correct else 0
        max_score += pts
        if is_correct:
            correct_count += 1
        results.append({
            "question_id": q_id,
            "type": question.get("type", ""),
            "question": question.get("question", ""),
            "options": question.get("options"),
            "correct": is_correct,
            "score": pts if is_correct else 0,
            "max_score": pts,
            "feedback": "正确" if is_correct else f"正确答案: {correct_answer}",
            "user_answer": user_answer,
            "correct_answer": correct_answer,
            "explanation": question.get("explanation") or f"正确答案是 {correct_answer}，请对照题目回顾相关知识点。",
        })
        if not is_correct:
            if quiz.scope == "wrong_review" and question.get("question", "") in wrong_by_question:
                wq = wrong_by_question[question.get("question", "")]
                wq.review_count += 1
                wq.last_reviewed_at = datetime.utcnow()
            else:
                wq = WrongQuestion(user_id=user_id, quiz_id=quiz.id, question=question, user_answer=user_answer, correct_answer=correct_answer, explanation=question.get("explanation", ""), error_type=question.get("type"))
                db.add(wq)
                await db.flush()
                suggested_reviews.append(SuggestedReview(wrong_id=wq.id, question=question, user_answer=user_answer, correct_answer=correct_answer, explanation=question.get("explanation", "")))
            wrong_questions.append({"id": str(wq.id), "question": question, "user_answer": user_answer, "correct_answer": correct_answer})
        elif quiz.scope == "wrong_review" and question.get("question", "") in wrong_by_question:
            wq = wrong_by_question[question.get("question", "")]
            wq.mastered = True
            wq.review_count += 1
            wq.last_reviewed_at = datetime.utcnow()

    quiz.answers = data.answers
    quiz.score = (total_score / max_score * 100) if max_score > 0 else 0
    quiz.correct_count = correct_count
    quiz.status = "completed"

    await _record_quiz_mastery(db, user_id, quiz, results, quiz_count=1)

    await db.commit()

    mastery_change = 10.0 if (correct_count / max(quiz.total_questions, 1)) >= 0.9 else 5.0 if (correct_count / max(quiz.total_questions, 1)) >= 0.7 else 0.0

    return QuizResult(
        quiz_id=quiz.id, score=float(quiz.score), total_questions=quiz.total_questions,
        correct_count=correct_count, results=results, wrong_questions=wrong_questions,
        suggested_reviews=suggested_reviews,
        mastery_change=mastery_change, time_spent_seconds=0
    )


@router.get("/wrong-book", response_model=List[WrongQuestionResponse])
async def list_wrong_book(
    limit: int = 50, offset: int = 0,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(WrongQuestion).where(WrongQuestion.user_id == user_id, WrongQuestion.mastered == False)
        .order_by(WrongQuestion.created_at.desc()).limit(limit).offset(offset)
    )
    wrongs = result.scalars().all()

    # 已加入复习计划的 topic 集合（source=quiz 且 active），用于标记 in_review
    rs = await db.execute(
        select(ReviewSchedule.topic).where(
            ReviewSchedule.user_id == user_id,
            ReviewSchedule.source == "quiz",
            ReviewSchedule.status == "active",
            ReviewSchedule.topic.isnot(None),
        )
    )
    review_topics = {row[0] for row in rs.fetchall()}

    items = []
    for wq in wrongs:
        resp = WrongQuestionResponse.model_validate(wq)
        q = wq.question or {}
        topic = (q.get("question") or "").strip()[:200]
        resp.in_review = topic in review_topics
        items.append(resp)
    return items


@router.post("/wrong-book/{wrong_id}/mastered")
async def mark_wrong_mastered(
    wrong_id: UUID,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(WrongQuestion).where(WrongQuestion.id == wrong_id, WrongQuestion.user_id == user_id)
    )
    wq = result.scalar_one_or_none()
    if not wq:
        raise HTTPException(status_code=404, detail="Wrong question not found")
    wq.mastered = True
    await db.commit()
    return {"status": "ok"}


@router.post("/wrong-book/add-to-review", response_model=AddToReviewResponse)
async def add_wrong_to_review(
    data: AddToReviewRequest,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db)
):
    """将错题加入复习计划（初始间隔 1 天, SM-2）"""
    if not data.wrong_ids:
        raise HTTPException(status_code=400, detail="No wrong questions")

    result = await db.execute(
        select(WrongQuestion).where(WrongQuestion.id.in_(data.wrong_ids), WrongQuestion.user_id == user_id)
    )
    wrongs = result.scalars().all()
    now = datetime.utcnow()

    added, skipped = 0, 0
    items = []
    for wq in wrongs:
        q = wq.question or {}
        topic = (q.get("question") or "").strip()[:200]
        if not topic:
            continue
        dup = await db.execute(
            select(ReviewSchedule).where(
                ReviewSchedule.user_id == user_id,
                ReviewSchedule.source == "quiz",
                ReviewSchedule.topic == topic,
                ReviewSchedule.status == "active",
            )
        )
        if dup.scalar_one_or_none():
            skipped += 1
            continue
        schedule = ReviewSchedule(
            user_id=user_id,
            chunk_id=None,
            topic=topic,
            answer=_resolve_review_answer(q, wq.correct_answer, wq.explanation),
            source="quiz",
            reason="wrong",
            next_review=compute_next_review_window(now),
            interval_days=1.0,
            ease_factor=2.5,
            review_count=0,
            mastery_score=10.0,
            status="active",
        )
        db.add(schedule)
        await db.flush()
        added += 1
        items.append({"wrong_id": str(wq.id), "schedule_id": str(schedule.id), "topic": topic, "next_review": schedule.next_review.isoformat()})

    await db.commit()
    return AddToReviewResponse(added=added, skipped=skipped, items=items)


def _resolve_review_answer(q: dict, correct_answer, explanation):
    """生成复习计划答案: 选择题将答案字母映射为选项内容, 简答题直接用答案"""
    letter = (correct_answer or "").strip()
    options = q.get("options") or {}
    content = options.get(letter) or (options.get(letter.upper()) if letter else None)
    if content:
        detail = content
    else:
        detail = letter or ""
    return f"正确答案: {detail}\n解析: {explanation or '无'}"


async def _load_wrong_questions(db, user_id, limit):
    """错题复习模式: 从未掌握错题出题"""
    result = await db.execute(
        select(WrongQuestion)
        .where(WrongQuestion.user_id == user_id, WrongQuestion.mastered == False)
        .order_by(WrongQuestion.created_at.asc())
    )
    wrongs = result.scalars().all()[:limit]
    if not wrongs:
        raise HTTPException(status_code=400, detail="暂无错题可复习，先去智能测验中答题吧")
    questions_data = []
    for i, wq in enumerate(wrongs):
        q = dict(wq.question or {})
        q["id"] = f"wq{i + 1}"
        q.setdefault("points", 20)
        q.setdefault("explanation", wq.explanation or "")
        questions_data.append(q)
    return questions_data


async def _get_knowledge_context(db, user_id, scope, topic, time_range):
    from shared.models import Document, Chunk
    if scope == "topic" and topic:
        result = await db.execute(
            select(Chunk.content)
            .join(Document, Chunk.document_id == Document.id)
            .where(Document.user_id == user_id, Document.deleted_at.is_(None), Chunk.content.ilike(f"%{topic}%"))
            .limit(10)
        )
        return "\n\n".join([row[0] for row in result.fetchall()])
    if scope == "time_range" and time_range:
        # time_range: {"days": N} 表示最近 N 天, {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"} 表示起止日期
        now = datetime.utcnow()
        if time_range.get("days") is not None:
            end = now
            start = now - timedelta(days=int(time_range["days"]))
        else:
            start = datetime.fromisoformat(time_range["start"]) if time_range.get("start") else datetime.min
            end = datetime.fromisoformat(time_range["end"]) if time_range.get("end") else now
        result = await db.execute(
            select(Chunk.content)
            .join(Document, Chunk.document_id == Document.id)
            .where(
                Document.user_id == user_id,
                Document.deleted_at.is_(None),
                Chunk.deleted_at.is_(None),
                Chunk.created_at >= start,
                Chunk.created_at <= end,
            )
            .limit(10)
        )
        contents = [row[0] for row in result.fetchall()]
        if contents:
            return "\n\n".join(contents)
    return "请基于通用编程知识生成测验。"


async def _collect_seen_questions(db, user_id, scope, topic, limit):
    """收集去重维度下已出过的题干(已生成测验题 + 已掌握错题). topic→同主题, 其余→用户近期全局."""
    questions = []
    if scope == "topic" and topic:
        q_result = await db.execute(
            select(Quiz.questions, Quiz.created_at)
            .where(Quiz.user_id == user_id, Quiz.scope == "topic", Quiz.topic == topic, Quiz.status.in_(["pending", "completed"]))
            .order_by(Quiz.created_at.desc()).limit(100)
        )
    else:
        q_result = await db.execute(
            select(Quiz.questions, Quiz.created_at)
            .where(Quiz.user_id == user_id, Quiz.status.in_(["pending", "completed"]))
            .order_by(Quiz.created_at.desc()).limit(100)
        )
    for questions_json, _ in q_result.fetchall():
        for q in (questions_json or []):
            text = (q.get("question") or "").strip()
            if text:
                questions.append(text)
        if len(questions) >= limit * 3:
            break
    wq_result = await db.execute(
        select(WrongQuestion.question)
        .where(WrongQuestion.user_id == user_id, WrongQuestion.mastered.is_(True))
        .order_by(WrongQuestion.created_at.desc()).limit(limit)
    )
    for (question_json,) in wq_result.fetchall():
        text = ((question_json or {}).get("question") or "").strip()
        if text:
            questions.append(text)
    return questions[:limit]


def _dedup_filter(questions_data, seen):
    """剔除与已出题相似度超阈值的题, 返回去重后的题列表."""
    if not seen:
        return questions_data
    kept = []
    for q in questions_data:
        text = (q.get("question") or "").strip()
        if not text:
            kept.append(q)
            continue
        if max(similarity(text, s) for s in seen) >= DEDUP_THRESHOLD:
            continue
        kept.append(q)
        seen.append(text)
    return kept
