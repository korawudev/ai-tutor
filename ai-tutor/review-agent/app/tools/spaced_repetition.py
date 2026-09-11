"""艾宾浩斯遗忘曲线算法 - 改良 SM-2 三分支版本"""
from datetime import datetime, timedelta
from typing import Tuple
from dataclasses import dataclass
from enum import Enum


class NormalReviewAnswer(str, Enum):
    """正式复习作答选项（前端3级映射后端5级）"""
    MASTERED = "mastered"      # 认识 -> quality 5
    VAGUE = "vague"            # 模糊 -> quality 3
    FORGOTTEN = "forgotten"    # 不认识 -> quality 0


@dataclass
class SpacedRepetitionResult:
    """间隔重复结果"""
    new_interval: float  # 新间隔（天）
    ease_factor: float   # 简易因子
    mastery_score: float # 掌握度
    correct_streak: int  # 连续正式答对计数
    status: str          # active, mastered
    need_session_retry: bool = False
    retry_reason: str = None  # "vague" | "forgotten"


def calculate_next_review(
    answer: NormalReviewAnswer,
    current_interval: float,
    ease_factor: float,
    mastery_score: float,
    correct_streak: int = 0
) -> SpacedRepetitionResult:
    """
    计算下次复习时间 - 改良 SM-2 三分支版本
    
    前端 3 级映射后端 5 级：
    - mastered (认识)     -> quality 5
    - vague (模糊)        -> quality 3  
    - forgotten (不认识)   -> quality 0
    
    Args:
        answer: 作答结果
        current_interval: 当前间隔（天）
        ease_factor: 简易因子
        mastery_score: 当前掌握度
        correct_streak: 连续正式答对计数
        
    Returns:
        SpacedRepetitionResult
    """
    old_ease_factor = ease_factor
    old_mastery = mastery_score
    old_streak = correct_streak
    
    if answer == NormalReviewAnswer.MASTERED:
        # 认识：正向 - quality 5
        # 间隔显著延长
        if correct_streak == 0:
            new_interval = 1.0
        elif correct_streak == 1:
            new_interval = 6.0
        else:
            new_interval = current_interval * ease_factor
            
        ease_factor = min(ease_factor + 0.15, 3.0)
        mastery_score = min(mastery_score + 15, 100)
        correct_streak += 1
        need_retry = False
        retry_reason = None
        
    elif answer == NormalReviewAnswer.VAGUE:
        # 模糊：小幅降级 quality 3
        # 间隔小幅缩短
        new_interval = max(1.0, current_interval * 0.5)
        ease_factor = max(ease_factor - 0.1, 1.3)
        mastery_score = max(mastery_score - 5, 0)
        correct_streak = 0
        need_retry = True
        retry_reason = "vague"
        
    else:  # FORGOTTEN
        # 不认识：大幅降级 quality 0
        # 重置间隔到最小
        new_interval = 1.0
        ease_factor = max(ease_factor - 0.2, 1.3)
        mastery_score = max(mastery_score - 15, 0)
        correct_streak = 0
        need_retry = True
        retry_reason = "forgotten"
    
    # 毕业判定：连续 3 次正式答对（mastered），与 mastery_score 分值解耦（产品文档 §11.3）
    status = "mastered" if correct_streak >= 3 else "active"
    
    return SpacedRepetitionResult(
        new_interval=new_interval,
        ease_factor=ease_factor,
        mastery_score=mastery_score,
        correct_streak=correct_streak,
        status=status,
        need_session_retry=need_retry,
        retry_reason=retry_reason
    )


def get_initial_interval() -> Tuple[float, float]:
    """
    获取初始间隔和简易因子
    
    Returns:
        (interval_days, ease_factor)
    """
    return (1.0, 2.5)


def calculate_mastery_score(
    quiz_accuracy: float,
    feynman_score: float,
    review_count: int,
    last_days: int
) -> float:
    """
    计算综合掌握度
    
    Args:
        quiz_accuracy: 测验正确率 (0-100)
        feynman_score: 费曼检测分数 (0-100)
        review_count: 复习次数
        last_days: 距离上次学习天数
        
    Returns:
        掌握度 (0-100)
    """
    # 权重
    w_quiz = 0.4
    w_feynman = 0.3
    w_review = 0.2
    w_recency = 0.1
    
    # 复习次数得分（对数衰减）
    review_score = min(100, 20 * (1 + 0.5 * review_count ** 0.5))
    
    # 时效性得分（7天内有效，之后衰减）
    recency_score = max(0, 100 - last_days * 15)
    
    # 综合得分
    score = (
        w_quiz * quiz_accuracy +
        w_feynman * feynman_score +
        w_review * review_score +
        w_recency * recency_score
    )
    
    return min(max(score, 0), 100)
