"""费曼学习法状态机"""
from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass


class FeynmanState(str, Enum):
    """费曼学习法状态"""
    INIT = "init"                    # 初始化会话
    LISTENING = "listening"          # 等待用户讲述
    EVALUATING = "evaluating"        # 评估解释
    GUIDING = "guiding"              # 引导追问
    COMPLETED = "completed"          # 生成评价
    AWAITING = "awaiting"            # 等待用户选择
    SAVED = "saved"                  # 写入复习调度


@dataclass
class FeynmanSessionState:
    """费曼会话状态"""
    state: FeynmanState = FeynmanState.INIT
    topic: str = ""
    tags: list = None
    reference_knowledge: str = ""
    conversation_history: list = None
    current_round: int = 0
    max_rounds: int = 10
    scores: dict = None
    gaps: list = None
    final_evaluation: dict = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.conversation_history is None:
            self.conversation_history = []
        if self.scores is None:
            self.scores = {
                "accuracy": 0,
                "clarity": 0,
                "completeness": 0
            }
        if self.gaps is None:
            self.gaps = []


class FeynmanStateMachine:
    """
    费曼学习法状态机
    
    管理费曼学习检测的完整流程
    """
    
    def __init__(self):
        self._transitions = {
            FeynmanState.INIT: [FeynmanState.LISTENING],
            FeynmanState.LISTENING: [FeynmanState.EVALUATING],
            FeynmanState.EVALUATING: [FeynmanState.GUIDING, FeynmanState.COMPLETED],
            FeynmanState.GUIDING: [FeynmanState.LISTENING],
            FeynmanState.COMPLETED: [FeynmanState.AWAITING],
            FeynmanState.AWAITING: [FeynmanState.SAVED],
            FeynmanState.SAVED: [],
        }
    
    def can_transition(self, current: FeynmanState, target: FeynmanState) -> bool:
        """
        检查是否可以进行状态转换
        
        Args:
            current: 当前状态
            target: 目标状态
        
        Returns:
            是否可以转换
        """
        return target in self._transitions.get(current, [])
    
    def transition(self, session: FeynmanSessionState, target: FeynmanState) -> FeynmanSessionState:
        """
        执行状态转换
        
        Args:
            session: 当前会话状态
            target: 目标状态
        
        Returns:
            更新后的会话状态
        
        Raises:
            ValueError: 如果无法进行转换
        """
        if not self.can_transition(session.state, target):
            raise ValueError(
                f"Cannot transition from {session.state} to {target}"
            )
        
        session.state = target
        return session
    
    def should_continue(self, session: FeynmanSessionState) -> bool:
        """
        判断是否应该继续引导追问
        
        Args:
            session: 当前会话状态
        
        Returns:
            是否继续
        """
        # 如果达到最大轮数，停止
        if session.current_round >= session.max_rounds:
            return False
        
        # 如果有未解决的 gaps，继续
        if session.gaps and len(session.gaps) > 0:
            return True
        
        # 如果总分低于 80，继续
        total_score = sum(session.scores.values())
        if total_score < 80:
            return True
        
        return False


# 全局实例
feynman_state_machine = FeynmanStateMachine()
