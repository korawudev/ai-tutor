"""Gateway API - Run 触发和流"""

import json
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.database import get_db
from shared.models import Run, RunCreate, RunResponse, Thread

from ..core.sse_manager import sse_manager
from .auth import get_user_id_dependency

router = APIRouter(prefix="/api/threads/{thread_id}/runs", tags=["runs"])

SILICONFLOW_API_KEY = "sk-cqcfucmaqkevzgdocujajqvriqallwavsimugmyuweaeykjv"
SILICONFLOW_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_MODEL = "deepseek-ai/DeepSeek-V3"

FEYNMAN_SYSTEM_PROMPT = """你是一位费曼学习法导师。你的任务是帮助用户通过"教别人"来深入理解概念。

核心原则：
1. 引导用户用自己的话解释概念，而不是死记硬背
2. 用苏格拉底式提问帮助用户发现理解中的盲点
3. 如果用户的解释有误或不清晰，温和地指出并引导他们重新思考
4. 用简单的类比和例子帮助用户建立直觉
5. 鼓励用户将复杂概念拆解成简单的部分

对话风格：
- 简洁、友好、有启发性
- 不要直接给出答案，而是引导用户自己发现
- 适当使用追问来深化理解
- 当用户理解正确时给予肯定

重要：当用户已经解释得足够清楚，或者对话已经进行了5轮以上，你认为用户已经理解了核心概念时，\
在回复末尾加上 [END] 标记。例如："你已经解释得很清楚了！[END]"
只在你认为对话可以结束时才加 [END]，不要过早结束。"""

RAG_SYSTEM_PROMPT = """你是一位知识助手。根据提供的知识库内容回答用户的问题。

规则：
1. 基于提供的上下文回答，不要编造信息
2. 如果上下文中没有相关信息，诚实说明
3. 回答要准确、简洁、有条理
4. 适当引用来源"""


async def _call_llm_stream(messages: list[dict], model: str = DEFAULT_MODEL):
    async with (
        httpx.AsyncClient() as client,
        client.stream(
            "POST",
            f"{SILICONFLOW_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": messages,
                "max_tokens": 2048,
                "temperature": 0.7,
                "stream": True,
            },
            timeout=60.0,
        ) as resp,
    ):
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                    delta = chunk["choices"][0].get("delta", {})
                    if "content" in delta:
                        yield delta["content"]
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue


async def _retrieve_context(query: str, top_k: int = 3) -> str:
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "http://knowledge-agent:8001/api/search",
                json={"query": query, "top_k": top_k},
                timeout=10.0,
            )
            if resp.status_code == 200:
                results = resp.json()
                chunks = results if isinstance(results, list) else results.get("results", [])
                return "\n\n".join(c.get("content", "") for c in chunks[:top_k] if c.get("content"))
    except Exception:
        pass
    return ""


@router.post("", response_model=RunResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    thread_id: UUID,
    run_data: RunCreate,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id, Thread.user_id == user_id),
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    input_data = run_data.input
    if isinstance(input_data, str):
        input_data = {"input": input_data}

    run = Run(
        thread_id=thread_id,
        agent_type=run_data.agent_type,
        input=input_data,
        status="pending",
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    if not thread.title:
        user_text = input_data.get("input", "") if isinstance(input_data, dict) else str(input_data)
        thread.title = user_text[:30] if user_text else "新对话"
        await db.commit()

    if run_data.agent_type == "feynman":
        return StreamingResponse(
            _feynman_stream(thread_id, run.id, run_data.input, db),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    response_text = _generate_simple_response(run_data.agent_type, run_data.input)
    run.output = {"response": response_text}
    run.status = "completed"
    await db.commit()

    return RunResponse.model_validate(run)


@router.get("", response_model=list[RunResponse])
async def list_runs(
    thread_id: UUID,
    limit: int = 10,
    offset: int = 0,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    """列出线程的 Run 记录（含已完成的对话历史）

    - limit: 返回数量（默认 10）
    - offset: 偏移量，用于上拉分页（offset 为第几批）
    - 按创建时间倒序返回（最新在前），用于"最近的 10 条消息"，offset 递增拉取更早的
    """
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id, Thread.user_id == user_id),
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    result = await db.execute(
        select(Run)
        .where(Run.thread_id == thread_id, Run.status == "completed")
        .order_by(Run.created_at.desc())
        .limit(limit)
        .offset(offset),
    )
    runs = result.scalars().all()

    return [RunResponse.model_validate(r) for r in runs]


async def _feynman_stream(thread_id: UUID, run_id: UUID, input_data: dict, db: AsyncSession):
    user_text = input_data.get("input", "") if isinstance(input_data, dict) else str(input_data)

    history_result = await db.execute(
        select(Run)
        .where(Run.thread_id == thread_id, Run.status == "completed", Run.id != run_id)
        .order_by(Run.created_at.desc())
        .limit(10),
    )
    history_runs = list(reversed(history_result.scalars().all()))

    context = await _retrieve_context(user_text)

    messages = [{"role": "system", "content": FEYNMAN_SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "system", "content": f"相关知识库内容：\n{context}"})
    for hr in history_runs:
        prev_input = hr.input.get("input", "") if isinstance(hr.input, dict) else str(hr.input)
        messages.append({"role": "user", "content": prev_input})
        if hr.output and isinstance(hr.output, dict) and hr.output.get("response"):
            messages.append({"role": "assistant", "content": hr.output["response"]})
    messages.append({"role": "user", "content": user_text})

    full_response = ""
    try:
        async for token in _call_llm_stream(messages):
            full_response += token
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        should_end = "[END]" in full_response
        clean_response = full_response.replace("[END]", "").strip()

        done_payload = {"type": "done", "response": clean_response, "should_end": should_end}
        yield f"data: {json.dumps(done_payload)}\n\n"

        run_result = await db.execute(select(Run).where(Run.id == run_id))
        run = run_result.scalar_one_or_none()
        if run:
            run.output = {"response": clean_response, "should_end": should_end}
            run.status = "completed"
            await db.commit()

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)[:200]})}\n\n"


def _generate_simple_response(agent_type: str, input_data: dict) -> str:
    user_input = input_data.get("input", "") if isinstance(input_data, dict) else str(input_data)

    if agent_type == "feynman":
        return (
            "作为费曼学习助手，我来帮您理解这个概念。您提到的是："
            f"{user_input[:100]}... 请尝试用自己的话解释这个概念，我会评估您的理解程度。"
        )
    if agent_type == "rag":
        return (
            "根据知识库的内容，关于您提到的"
            f"'{user_input[:50]}'，我为您整理了相关信息。这是一个很好的问题！"
        )
    return f"收到您的消息：{user_input[:100]}... 正在处理中。"


@router.get("/stream")
async def stream_events(
    thread_id: UUID,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id, Thread.user_id == user_id),
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    return StreamingResponse(
        sse_manager.event_generator(thread_id),
        media_type="text/event-stream",
    )


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    thread_id: UUID,
    run_id: UUID,
    user_id: UUID = Depends(get_user_id_dependency),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Thread).where(Thread.id == thread_id, Thread.user_id == user_id),
    )
    thread = result.scalar_one_or_none()

    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")

    result = await db.execute(
        select(Run).where(Run.id == run_id, Run.thread_id == thread_id),
    )
    run = result.scalar_one_or_none()

    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    return RunResponse.model_validate(run)
