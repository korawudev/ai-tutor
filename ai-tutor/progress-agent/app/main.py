"""Progress Agent 服务 - 主入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.utils.config import settings

app = FastAPI(
    title="AI Tutor Progress Agent",
    description="AI 私教系统 - 进度追踪",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "progress-agent"}


@app.get("/")
async def root():
    return {
        "service": "AI Tutor Progress Agent",
        "version": "0.1.0",
        "docs": "/docs"
    }
