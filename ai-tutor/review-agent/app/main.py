"""Review Agent 服务 - 主入口"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Tutor Review Agent",
    description="AI 私教系统 - 复习调度",
    version="0.1.0",
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
    return {"status": "healthy", "service": "review-agent"}


@app.get("/")
async def root():
    return {
        "service": "AI Tutor Review Agent",
        "version": "0.1.0",
        "docs": "/docs",
    }
