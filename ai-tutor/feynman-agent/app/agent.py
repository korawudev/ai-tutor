"""费曼学习法 Agent"""
from typing import Dict, Any, Optional, List
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Chunk
from shared.llm import llm_router
from .state_machine import FeynmanStateMachine, FeynmanSessionState, FeynmanState, feynman_state_machine
from .evaluator import feynman_evaluator
from .tools import (
    evaluate_explanation,
    generate_final_evaluation,
    generate_welcome_message,
    generate_guidance_message,
    generate_final_message
)


class FeynmanAgent:
    """
    费曼学习法 Agent
    
    管理费曼学习检测的完整流程
    """
    
    def __init__(self):
        self.state_machine = feynman_state_machine
    
    async def start_session(
        self,
        db: AsyncSession,
        user_id: UUID,
        topic: str,
        tags: List[str],
        reference_knowledge: str
    ) -> Dict[str, Any]:
        """
        开始费曼学习会话
        
        Args:
            db: 数据库会话
            user_id: 用户 ID
            topic: 主题
            tags: 标签
            reference_knowledge: 参考知识
        
        Returns:
            初始响应
        """
        # 创建会话状态
        session = FeynmanSessionState(
            state=FeynmanState.INIT,
            topic=topic,
            tags=tags,
            reference_knowledge=reference_knowledge
        )
        
        # 状态转换到 LISTENING
        session = self.state_machine.transition(session, FeynmanState.LISTENING)
        
        # 生成欢迎消息
        welcome_message = generate_welcome_message(topic, tags)
        
        return {
            "session_state": session,
            "message": welcome_message,
            "requires_input": True
        }
    
    async def process_explanation(
        self,
        session: FeynmanSessionState,
        user_explanation: str
    ) -> Dict[str, Any]:
        """
        处理用户解释
        
        Args:
            session: 当前会话状态
            user_explanation: 用户解释
        
        Returns:
            处理结果
        """
        # 记录对话历史
        session.conversation_history.append({
            "role": "user",
            "content": user_explanation
        })
        
        # 状态转换到 EVALUATING
        session = self.state_machine.transition(session, FeynmanState.EVALUATING)
        
        # 评估解释
        evaluation = await evaluate_explanation(
            user_explanation,
            session.reference_knowledge,
            session.topic,
            session.conversation_history
        )
        
        # 更新会话状态
        session.current_round += 1
        session.scores = evaluation.dimensions
        session.gaps = evaluation.gaps
        
        # 判断是否继续引导
        if self.state_machine.should_continue(session):
            # 继续引导
            session = self.state_machine.transition(session, FeynmanState.GUIDING)
            
            guidance_message = generate_guidance_message(evaluation, session.topic)
            
            session.conversation_history.append({
                "role": "assistant",
                "content": guidance_message
            })
            
            return {
                "session_state": session,
                "message": guidance_message,
                "evaluation": {
                    "round": session.current_round,
                    "score": evaluation.score,
                    "dimensions": evaluation.dimensions,
                    "gaps": evaluation.gaps
                },
                "requires_input": True,
                "should_continue": True
            }
        else:
            # 完成评估
            session = self.state_machine.transition(session, FeynmanState.COMPLETED)
            
            # 生成最终评价
            final_evaluation = await generate_final_evaluation(
                session.conversation_history,
                session.reference_knowledge,
                session.topic
            )
            
            session.final_evaluation = final_evaluation
            
            # 转换到 AWAITING 状态
            session = self.state_machine.transition(session, FeynmanState.AWAITING)
            
            final_message = generate_final_message(final_evaluation)
            
            return {
                "session_state": session,
                "message": final_message,
                "evaluation": final_evaluation,
                "requires_input": True,
                "should_continue": False,
                "review_candidates": self._extract_review_candidates(final_evaluation)
            }
    
    async def add_to_review(
        self,
        session: FeynmanSessionState,
        selected_concepts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        将选中的知识点加入复习
        
        Args:
            session: 当前会话状态
            selected_concepts: 选中的知识点
        
        Returns:
            处理结果
        """
        # 如果状态转换不合法，则直接设置为 SAVED
        if self.state_machine.can_transition(session.state, FeynmanState.SAVED):
            session = self.state_machine.transition(session, FeynmanState.SAVED)
        else:
            session.state = FeynmanState.SAVED
        
        return {
            "session_state": session,
            "message": f"已将 {len(selected_concepts)} 个知识点加入复习计划。",
            "added_count": len(selected_concepts),
            "concepts": selected_concepts
        }
    
    def _extract_review_candidates(self, evaluation: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        提取复习候选知识点
        
        Args:
            evaluation: 最终评价
        
        Returns:
            复习候选列表
        """
        candidates = []
        
        # 理解错误的部分
        for item in evaluation.get("understood_wrong", []):
            candidates.append({
                "concept": item.get("concept", ""),
                "reason": "wrong",
                "importance": "high"
            })
        
        # 记忆模糊的部分
        for item in evaluation.get("unclear", []):
            candidates.append({
                "concept": item.get("concept", ""),
                "reason": "unclear",
                "importance": item.get("importance", "medium")
            })
        
        return candidates


# 全局实例
feynman_agent = FeynmanAgent()
