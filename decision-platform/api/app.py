"""FastAPI 应用实例 — 工厂函数 + lifespan。

Phase 4 Day 31 基础版：注册 query_router，无鉴权中间件。
Day 32 加入 auth_router + JWT middleware + DB 建表。
Day 34 加入 export_router。
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from utils.logger import log_agent_step


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """应用生命周期：启动时建表，关闭时释放 DB 连接池。

    Day 32：Base.metadata.create_all 手动建 users 表。
            Day 36 引入 Alembic 后改为基线迁移。
    Day 35：检查 Redis / ChromaDB 连接状态。
    """
    log_agent_step("API", "启动", "Vantage API 启动中...")

    # Day 32: 初始化 DB 引擎 + 建表（Alembic 到 Day 36 接管）
    from models import engine, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log_agent_step("API", "DB", "数据库表初始化完成")

    yield

    await engine.dispose()
    log_agent_step("API", "关闭", "Vantage API 已停止。")


def create_app() -> FastAPI:
    """创建并配置 FastAPI 应用（工厂模式）。

    Returns:
        FastAPI: 配置好的应用实例，可直接 `uvicorn api.app:app --reload`。
    """
    app = FastAPI(
        title="Vantage API",
        description="企业智能决策中台 — 自然语言 → SQL + RAG → Markdown 分析报告",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS：本地开发允许所有来源，生产环境需收紧
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 注册路由
    from api.routes.query import router as query_router
    app.include_router(query_router)

    # Day 32: 认证路由
    from api.routes.auth import router as auth_router
    app.include_router(auth_router)

    # Day 34 注册：
    # from api.routes.export import router as export_router
    # app.include_router(export_router, prefix="/export")

    return app


# 模块级实例：uvicorn 直接 import 用
app = create_app()
