"""Gateway API - HITL 恢复"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.models import HITLResume, Run, RunResponse, Thread

from ..core.sse_manager import sse_manager
from .auth import get_user_id_dependency

router = APIRouter(prefix="/api/threads/{thread_id}/runs/{run_id}", tags=["hitl"])


@router.post("/resume", response_model=RunResponse)
async def resume_run(
    thread_id: UUID,
    run_id: UUID,
    resume_data: HITLResume,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """
    HITL 恢复 - 用于所有需要用户决策的场景

    - action: 动作类型 (add_to_review, handle_duplicate, scrape_fallback, continue_quiz)
    - input: 动作参数
    """
    # 验证 Thread 存在且属于当前用户
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id, Thread.user_id == user_id),
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Thread not found",
        )

    # 获取 Run
    result = await db.execute(
        select(Run).where(Run.id == run_id, Run.thread_id == thread_id),
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found",
        )

    if run.status != "waiting_hitl":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run is not waiting for HITL",
        )

    # 更新 Run 状态
    run.status = "running"
    run.input = {**run.input, "hitl_response": resume_data.input}
    await db.commit()

    # TODO: 异步继续 Agent 执行
    # 这里应该发送消息到 Agent 服务

    # 推送 HITL 恢复事件
    await sse_manager.emit(
        thread_id,
        "hitl_resumed",
        {"run_id": str(run_id), "action": resume_data.action},
        run_id,
    )

    return RunResponse.model_validate(run)
