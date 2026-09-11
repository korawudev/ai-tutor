"""数据模型 - User"""

from datetime import datetime
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy import JSON, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    avatar_url = Column(String(500), nullable=True)
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)


# Pydantic Schemas
class UserCreate(BaseModel):
    """创建用户请求"""

    email: str
    username: str
    password: str


class UserResponse(BaseModel):
    """用户响应"""

    id: UUID
    email: str
    username: str
    avatar_url: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserLogin(BaseModel):
    """用户登录请求"""

    email: str
    password: str


class Token(BaseModel):
    """JWT Token 响应"""

    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
