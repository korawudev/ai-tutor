"""费曼 Agent 服务 - 主入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.utils.config import settings
from .api.routes import router as feynman_router

app = FastAPI(
    title="AI Tutor Feynman Agent",
    description="AI 私教系统 - 费曼学习法检测",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(feynman_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "feynman-agent"}


@app.get("/")
async def root():
    return {
        "service": "AI Tutor Feynman Agent",
        "version": "0.1.0",
        "docs": "/docs"
    }
