"""RAG Agent 服务 - 主入口"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.database import init_db

from .api import search_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    await init_db()
    yield


app = FastAPI(
    title="AI Tutor RAG Agent",
    description="AI 私教系统 - RAG 检索服务",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search_router)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "rag-agent"}


@app.get("/")
async def root():
    return {
        "service": "AI Tutor RAG Agent",
        "version": "0.1.0",
        "docs": "/docs",
    }
