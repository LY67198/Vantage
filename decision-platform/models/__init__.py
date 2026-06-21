"""SQLAlchemy 2.0 async ORM 基础设施。

- DeclarativeBase + async engine + session factory + get_db 依赖。
- Day 32：先用 Base.metadata.create_all() 手动建 users 表。
- Day 36：引入 Alembic，通过基线迁移纳管。
"""

import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres@localhost:5432/vantage",
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_size=5)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""
    pass


async def get_db() -> AsyncSession:
    """FastAPI Depends 注入用 — 每个请求一个 session，响应后自动关闭。"""
    async with async_session() as session:
        yield session
