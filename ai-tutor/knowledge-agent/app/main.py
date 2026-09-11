"""Knowledge Agent 服务 - 主入口"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.utils.config import settings
from shared.database import init_db
from .api import documents_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期"""
    # 启动时初始化数据库
    await init_db()
    yield
    # 关闭时清理资源


app = FastAPI(
    title="AI Tutor Knowledge Agent",
    description="AI 私教系统 - 知识摄入服务",
    version="0.1.0",
    lifespan=lifespan
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(documents_router)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "knowledge-agent"}


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "AI Tutor Knowledge Agent",
        "version": "0.1.0",
        "docs": "/docs"
    }
