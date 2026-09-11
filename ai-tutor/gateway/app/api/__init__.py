"""Gateway API"""

from .auth import router as auth_router
from .documents import router as documents_router
from .feynman import router as feynman_router
from .hitl import router as hitl_router
from .progress import router as progress_router
from .quiz import router as quiz_router
from .review import router as review_router
from .runs import router as runs_router
from .threads import router as threads_router

__all__ = [
    "auth_router",
    "threads_router",
    "runs_router",
    "hitl_router",
    "quiz_router",
    "review_router",
    "progress_router",
    "feynman_router",
    "documents_router",
]
