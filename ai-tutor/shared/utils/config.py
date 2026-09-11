"""配置管理"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """应用配置"""

    # ---------- 数据库 ----------
    DATABASE_URL: str = "postgresql+asyncpg://ai_tutor:postgres@localhost:5432/ai_tutor"

    # ---------- Redis ----------
    REDIS_URL: str = "redis://localhost:6379/0"

    # ---------- JWT ----------
    JWT_SECRET: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # ---------- LLM (硅基流动) ----------
    SILICONFLOW_API_KEY: str = ""
    SILICONFLOW_BASE_URL: str = "https://api.siliconflow.cn/v1"

    # 备用 LLM provider（选配，配置后 llm_router 可在主 provider 失败时自动切换）
    DEEPSEEK_API_KEY: str | None = None
    QWEN_API_KEY: str | None = None
    GLM_API_KEY: str | None = None

    # 默认模型
    DEFAULT_LLM_MODEL: str = "deepseek-ai/DeepSeek-V3"
    DEFAULT_EMBEDDING_MODEL: str = "BAAI/bge-m3"
    DEFAULT_RERANKER_MODEL: str = "BAAI/bge-reranker-v2-m3"

    # ---------- Jina Reader (可选) ----------
    JINA_API_KEY: str | None = None

    # ---------- Langfuse (可观测性) ----------
    LANGFUSE_HOST: str | None = None
    LANGFUSE_PUBLIC_KEY: str | None = None
    LANGFUSE_SECRET_KEY: str | None = None

    # ---------- Agent 服务端口 ----------
    KNOWLEDGE_AGENT_URL: str = "http://localhost:8001"
    RAG_AGENT_URL: str = "http://localhost:8002"
    FEYNMAN_AGENT_URL: str = "http://localhost:8003"
    QUIZ_AGENT_URL: str = "http://localhost:8004"
    REVIEW_AGENT_URL: str = "http://localhost:8005"
    PROGRESS_AGENT_URL: str = "http://localhost:8006"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
