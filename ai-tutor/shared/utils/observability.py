"""结构化日志 + Langfuse 追踪配置"""

import os
import sys
from typing import Any

import structlog

# Langfuse 初始化（可选：环境变量缺失时降级为无追踪）
_langfuse_client: Any = None


def get_langfuse() -> Any:
    """延迟获取 Langfuse 客户端，环境变量未设置时返回 None"""
    global _langfuse_client
    if _langfuse_client is None:
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        if public_key and secret_key:
            try:
                from langfuse import Langfuse

                _langfuse_client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host,
                )
            except Exception:
                _langfuse_client = False  # 标记失败，避免重试
    return _langfuse_client if _langfuse_client is not False else None


def setup_logging(log_level: str = "INFO") -> None:
    """配置 structlog 处理器链"""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(sys.modules.get("logging", __import__("logging")), log_level.upper(), 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """获取结构化日志实例"""
    return structlog.get_logger(name)
