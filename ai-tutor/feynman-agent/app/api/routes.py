"""费曼 Agent API 路由"""

from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..agent import feynman_agent

router = APIRouter(tags=["feynman"])

# In-memory session store (thread_id -> FeynmanSessionState)
_sessions: dict[str, object] = {}


class FeynmanStartRequest(BaseModel):
    user_id: str | None = None
    topic: str
    knowledge_context: str | None = None


class FeynmanExplainRequest(BaseModel):
    user_id: str | None = None
    thread_id: str
    explanation: str


class FeynmanAddReviewRequest(BaseModel):
    user_id: str | None = None
    thread_id: str
    chunk_id: str | None = None


@router.post("/start")
async def start_feynman(data: FeynmanStartRequest):
    """开始费曼学习会话"""
    thread_id = str(uuid4())

    session = await feynman_agent.start_session(
        _db=None,
        _user_id=UUID(data.user_id) if data.user_id else uuid4(),
        topic=data.topic,
        tags=[],
        reference_knowledge=data.knowledge_context or "",
    )
    _sessions[thread_id] = session["session_state"]

    return {
        "thread_id": thread_id,
        "message": session["message"],
        "requires_input": True,
        "state": session["session_state"].state.value,
    }


@router.post("/explain")
async def submit_explanation(data: FeynmanExplainRequest):
    """提交费曼解释"""
    session = _sessions.get(data.thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="Feynman session not found")

    result = await feynman_agent.process_explanation(session, data.explanation)
    _sessions[data.thread_id] = result["session_state"]

    return {
        "thread_id": data.thread_id,
        "message": result["message"],
        "evaluation": result.get("evaluation"),
        "requires_input": result.get("requires_input", True),
        "should_continue": result.get("should_continue", False),
        "review_candidates": result.get("review_candidates", []),
    }


@router.post("/add-to-review")
async def add_to_review(data: FeynmanAddReviewRequest):
    """将知识点加入复习计划"""
    session = _sessions.get(data.thread_id)
    if not session:
        raise HTTPException(status_code=404, detail="Feynman session not found")

    # Select review candidates from final evaluation
    selected = [
        {
            "concept": data.chunk_id or session.topic,
            "reason": "feynman_review",
        },
    ]

    result = await feynman_agent.add_to_review(session, selected)
    _sessions[data.thread_id] = result["session_state"]

    return {
        "thread_id": data.thread_id,
        "message": result["message"],
        "added_count": result["added_count"],
    }
