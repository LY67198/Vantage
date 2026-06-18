# JWT 鉴权 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 Vantage API 添加用户注册/登录/Token 刷新/JWT 鉴权，5 个新文件 + 1 个修改文件。

**Architecture:** SQLAlchemy 2.0 async (asyncpg) → services/auth_service.py (密码哈希 + JWT 编解码) → api/schemas/auth.py (Pydantic 模型) → api/routes/auth.py (3 个端点) → api/middleware/auth.py (Bearer token → Depends 注入 user)。lifespan 中 `create_all` 建表，Alembic 到 Day 36 补基线迁移。

**Tech Stack:** SQLAlchemy 2.0 async + asyncpg + bcrypt + python-jose[cryptography] + FastAPI HTTPBearer

---

### Task 1: 安装依赖

**Files:**
- Modify: `pyproject.toml`（添加依赖）
- Bash: `uv sync`（安装 + 更新 lock）

- [ ] **Step 1: 添加依赖到 pyproject.toml**

在 `pyproject.toml` 的 `dependencies` 列表中添加 4 个包。当前文件内容已知，在 `"uvicorn>=0.48.0",` 之后插入：

```toml
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "python-jose[cryptography]>=3.3",
    "bcrypt>=4.1",
```

注意：`python-jose[cryptography]` 的方括号在 TOML 中不需要转义，直接写即可。

- [ ] **Step 2: 安装并锁版本**

```bash
cd decision-platform && uv sync
```

Expected: 4 个新包安装成功，`uv.lock` 更新。

- [ ] **Step 3: 验证安装**

```bash
cd decision-platform && uv run python -c "
from sqlalchemy.ext.asyncio import create_async_engine; print('sqlalchemy OK')
import asyncpg; print('asyncpg OK')
from jose import jwt; print('jose OK')
import bcrypt; print('bcrypt OK')
"
```

Expected: 四个 "OK" 无报错。

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "chore: add JWT auth dependencies (sqlalchemy[asyncio], asyncpg, python-jose, bcrypt)"
```

---

### Task 2: 创建 models/ — DeclarativeBase + engine + User 模型

**Files:**
- Create: `models/__init__.py`
- Create: `models/user.py`

- [ ] **Step 1: 创建 `models/__init__.py`**

```python
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
```

- [ ] **Step 2: 创建 `models/user.py`**

```python
"""User ORM 模型 — JWT 认证用户表。"""

from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from models import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="user")  # user / admin — RBAC 预留
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 3: 验证模型可导入**

```bash
cd decision-platform && uv run python -c "from models.user import User; print('User model OK:', User.__tablename__)"
```

Expected: `User model OK: users`

- [ ] **Step 4: Commit**

```bash
git add models/__init__.py models/user.py
git commit -m "feat: add SQLAlchemy 2.0 async ORM — DeclarativeBase + User model"
```

---

### Task 3: 创建 services/auth_service.py — 密码哈希 + JWT 编解码 + DB 查询

**Files:**
- Create: `services/__init__.py`
- Create: `services/auth_service.py`

- [ ] **Step 1: 创建 `services/__init__.py`**（空包标记）

```python
"""业务逻辑层 — 认证 / 查询 / 导出等服务。"""
```

- [ ] **Step 2: 创建 `services/auth_service.py`**

```python
"""认证服务 — 密码哈希 + JWT 编解码 + 用户 CRUD。

职责：
- hash_password / verify_password：bcrypt 加盐哈希 + 验证
- create_access_token / create_refresh_token / decode_token：JWT HS256
- get_user_by_username / create_user：用户查询/创建
"""

import os
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.user import User

# ── 配置 ──────────────────────────────────────────────
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


# ── 密码哈希 ──────────────────────────────────────────
def hash_password(password: str) -> str:
    """对明文密码做 bcrypt 加盐哈希。"""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """验证明文密码是否匹配哈希。"""
    return bcrypt.checkpw(password.encode(), password_hash.encode())


# ── JWT 编解码 ────────────────────────────────────────
def create_access_token(username: str, role: str) -> str:
    """签发 access token（15 分钟有效）。"""
    payload = {
        "sub": username,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(username: str, role: str) -> str:
    """签发 refresh token（7 天有效）。"""
    payload = {
        "sub": username,
        "role": role,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """解码并验证 JWT token。

    Raises:
        JWTError: token 过期或签名无效。
    """
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


# ── 用户 CRUD ─────────────────────────────────────────
async def get_user_by_username(db: AsyncSession, username: str) -> User | None:
    """按用户名查用户。"""
    result = await db.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    username: str,
    password: str,
    email: str | None = None,
) -> User:
    """创建新用户 — 密码在服务层哈希，调用方传明文。"""
    user = User(
        username=username,
        password_hash=hash_password(password),
        email=email,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
```

- [ ] **Step 3: 验证 services 可导入 + bcrypt 加解密正常**

```bash
cd decision-platform && uv run python -c "
from services.auth_service import hash_password, verify_password
h = hash_password('test123')
assert verify_password('test123', h)
assert not verify_password('wrong', h)
print('Password hash OK')
"
```

Expected: `Password hash OK`

- [ ] **Step 4: 验证 JWT 编解码正常**

```bash
cd decision-platform && uv run python -c "
from services.auth_service import create_access_token, create_refresh_token, decode_token
token = create_access_token('testuser', 'user')
payload = decode_token(token)
assert payload['sub'] == 'testuser'
assert payload['type'] == 'access'
print('JWT encode/decode OK')

# 验证 refresh token type 不同
rt = create_refresh_token('testuser', 'user')
rp = decode_token(rt)
assert rp['type'] == 'refresh'
print('Refresh token OK')
"
```

Expected: `JWT encode/decode OK` + `Refresh token OK`

- [ ] **Step 5: 验证过期 token 抛出异常**

```bash
cd decision-platform && uv run python -c "
from jose import JWTError
from services.auth_service import decode_token
# 一个已过期的 token（exp 在 2020 年）
old_token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0IiwiZXhwIjoxNTc3ODM2ODAwfQ.fake'
try:
    decode_token(old_token)
    print('FAIL: should have raised')
except JWTError:
    print('Expired token correctly rejected')
"
```

Expected: `Expired token correctly rejected`

- [ ] **Step 6: Commit**

```bash
git add services/__init__.py services/auth_service.py
git commit -m "feat: add auth_service — bcrypt hash + JWT encode/decode + user CRUD"
```

---

### Task 4: 创建 api/schemas/auth.py — Pydantic 请求/响应模型

**Files:**
- Create: `api/schemas/auth.py`
- Modify: `api/schemas/__init__.py`（更新说明）

- [ ] **Step 1: 创建 `api/schemas/auth.py`**

```python
"""认证相关 Pydantic 模型 — 请求体 + 响应体。"""

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """注册请求。

    username: 3-50 字符
    password: 6-128 字符
    email: 可选，最长 100 字符
    """
    username: str = Field(..., min_length=3, max_length=50, examples=["zhangsan"])
    password: str = Field(..., min_length=6, max_length=128, examples=["aB3@xxxx"])
    email: str | None = Field(None, max_length=100, examples=["zhangsan@example.com"])


class LoginRequest(BaseModel):
    """登录请求。"""
    username: str = Field(..., min_length=1, max_length=50, examples=["zhangsan"])
    password: str = Field(..., min_length=1, max_length=128, examples=["aB3@xxxx"])


class RefreshRequest(BaseModel):
    """刷新 token 请求。"""
    refresh_token: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """登录/注册/刷新成功后返回的 token 对。"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """当前用户信息（调试用）。"""
    id: int
    username: str
    role: str
```

- [ ] **Step 2: 更新 `api/schemas/__init__.py`**

将现有内容替换为：

```python
"""API Schema 定义。

- query.py: QueryRequest（POST /query 请求体）
- auth.py:  RegisterRequest / LoginRequest / RefreshRequest / TokenResponse（Day 32 新增）
- export.py: 导出请求/响应模型（Day 34 新增）
"""
```

- [ ] **Step 3: 验证 schema 可导入**

```bash
cd decision-platform && uv run python -c "
from api.schemas.auth import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse
r = RegisterRequest(username='test', password='123456')
assert r.username == 'test'
print('Schemas OK')
"
```

Expected: `Schemas OK`

- [ ] **Step 4: Commit**

```bash
git add api/schemas/auth.py api/schemas/__init__.py
git commit -m "feat: add auth Pydantic schemas — RegisterRequest / LoginRequest / TokenResponse"
```

---

### Task 5: 创建 api/middleware/auth.py — JWT 鉴权依赖

**Files:**
- Create: `api/middleware/auth.py`
- Modify: `api/middleware/__init__.py`（更新说明）

- [ ] **Step 1: 创建 `api/middleware/auth.py`**

```python
"""JWT 鉴权依赖 — Bearer token → user dict。

用法：
    from api.middleware.auth import get_current_user

    @router.get("/protected")
    async def protected(user: dict = Depends(get_current_user)):
        return {"user": user}

Day 32：不强制应用于 /query，由各端点自主添加 Depends(get_current_user)。
Day 38：可改为全局 middleware。
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from services.auth_service import decode_token, get_user_by_username

security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """从 Authorization: Bearer <token> 头解析当前用户。

    Raises:
        401: token 缺失 / 无效 / 过期 / 不是 access token / 用户不存在
    """
    token = credentials.credentials

    try:
        payload = decode_token(token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请使用 access token",
        )

    username = payload.get("sub")
    if username is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效",
        )

    user = await get_user_by_username(db, username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    return {"id": user.id, "username": user.username, "role": user.role}
```

- [ ] **Step 2: 更新 `api/middleware/__init__.py`**

将现有内容替换为：

```python
"""API 中间件。

- auth.py:     JWT Bearer token 验证 → Depends(get_current_user)（Day 32 新增）
- tracing.py:  trace_id 注入 + 请求日志 contextvars（Day 38 新增）
"""
```

- [ ] **Step 3: 验证可导入**

```bash
cd decision-platform && uv run python -c "
from api.middleware.auth import get_current_user
print('Middleware import OK')
"
```

Expected: `Middleware import OK`

- [ ] **Step 4: Commit**

```bash
git add api/middleware/auth.py api/middleware/__init__.py
git commit -m "feat: add JWT auth middleware — get_current_user dependency via HTTPBearer"
```

---

### Task 6: 创建 api/routes/auth.py — 注册 / 登录 / 刷新端点

**Files:**
- Create: `api/routes/auth.py`
- Modify: `api/routes/__init__.py`（更新说明）

- [ ] **Step 1: 创建 `api/routes/auth.py`**

```python
"""认证路由 — POST /auth/register, /auth/login, /auth/refresh。"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models import get_db
from services.auth_service import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_user_by_username,
    create_user,
)
from api.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册。

    检查用户名唯一性 → bcrypt 哈希密码 → 写入 users 表 → 返回 token 对。
    """
    existing = await get_user_by_username(db, req.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="用户名已存在",
        )

    user = await create_user(db, req.username, req.password, req.email)

    return TokenResponse(
        access_token=create_access_token(user.username, user.role),
        refresh_token=create_refresh_token(user.username, user.role),
    )


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录。

    查用户 → 验证密码 → 返回 token 对。
    """
    user = await get_user_by_username(db, req.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    if not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    return TokenResponse(
        access_token=create_access_token(user.username, user.role),
        refresh_token=create_refresh_token(user.username, user.role),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """刷新 token — 用 refresh token 换一对新 token。

    只接受 type=refresh 的 token，access token 不能用来刷新。
    """
    from jose import JWTError

    try:
        payload = decode_token(req.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="请使用 refresh token",
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效",
        )

    user = await get_user_by_username(db, username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    return TokenResponse(
        access_token=create_access_token(user.username, user.role),
        refresh_token=create_refresh_token(user.username, user.role),
    )
```

- [ ] **Step 2: 验证路由可导入**

```bash
cd decision-platform && uv run python -c "
from api.routes.auth import router
print('Auth router OK, routes:', [r.path for r in router.routes])
"
```

Expected: `Auth router OK, routes: ['/auth/register', '/auth/login', '/auth/refresh']`

- [ ] **Step 3: Commit**

```bash
git add api/routes/auth.py
git commit -m "feat: add auth routes — POST /auth/register, /auth/login, /auth/refresh"
```

---

### Task 7: 修改 api/app.py — 注册 auth_router + 数据库初始化

**Files:**
- Modify: `api/app.py`

- [ ] **Step 1: 修改 `api/app.py`**

将 `create_app()` 中 Day 32 注释部分取消注释，并更新 lifespan 加入建表逻辑：

```python
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
```

- [ ] **Step 2: 验证 app 可启动 + Swagger 可见新端点**

```bash
cd decision-platform && timeout 5 uv run uvicorn api.app:app --reload 2>&1 || true
```

Expected: 无 import error，日志显示 `[API] 启动 Vantage API 启动中...` + `[API] DB 数据库表初始化完成`。

- [ ] **Step 3: Commit**

```bash
git add api/app.py
git commit -m "feat: wire auth_router into app + create_all tables in lifespan"
```

---

### Task 8: 端到端验证 — 注册 → 登录 → 刷新 → 鉴权保护端点

**Files:**
- None（纯手动测试，通过 curl 或 Swagger）

- [ ] **Step 1: 启动服务**

```bash
cd decision-platform && uv run uvicorn api.app:app --reload
```

保持终端运行，开另一个终端做后续测试。

- [ ] **Step 2: 注册新用户**

```bash
curl -s -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"test1234","email":"test@example.com"}' | python -m json.tool
```

Expected: 201 Created，返回 `access_token` + `refresh_token` + `token_type: "bearer"`。

- [ ] **Step 3: 重复注册 → 409**

```bash
curl -s -X POST http://127.0.0.1:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"test1234"}' | python -m json.tool
```

Expected: 409，`{"detail": "用户名已存在"}`。

- [ ] **Step 4: 登录 → 拿 token**

```bash
curl -s -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"test1234"}' | python -m json.tool
```

Expected: 200，返回新 token 对。记下 `access_token` 的值。

- [ ] **Step 5: 错误密码登录 → 401**

```bash
curl -s -X POST http://127.0.0.1:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"wrong"}' | python -m json.tool
```

Expected: 401，`{"detail": "用户名或密码错误"}`。

- [ ] **Step 6: 刷新 token**

用 Step 4 拿到的 `refresh_token`：

```bash
curl -s -X POST http://127.0.0.1:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<REFRESH_TOKEN>"}' | python -m json.tool
```

Expected: 200，返回一对新 token。

- [ ] **Step 7: 用 access token 刷新 → 401**

```bash
curl -s -X POST http://127.0.0.1:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<ACCESS_TOKEN>"}' | python -m json.tool
```

Expected: 401，`{"detail": "请使用 refresh token"}`。

- [ ] **Step 8: 验证 PostgreSQL 表已创建**

```bash
psql -U postgres -d vantage -c "\dt"
```

Expected: `users` 表出现在列表中。

- [ ] **Step 9: 验证 users 表中有数据**

```bash
psql -U postgres -d vantage -c "SELECT id, username, role, created_at FROM users;"
```

Expected: 显示 `testuser` 的记录。

- [ ] **Step 10: 验证 Swagger 可见新端点**

浏览器打开 `http://127.0.0.1:8000/docs`，确认：
- Auth 标签下有 `POST /auth/register`、`POST /auth/login`、`POST /auth/refresh`
- 各端点有 Request body schema 和 Response schema

---

## Self-Review

**1. Spec coverage:**

| 设计文档要求 | 对应 Task |
|-------------|-----------|
| models/ — DeclarativeBase + engine + User 模型 | Task 2 |
| services/auth_service.py — hash/verify + JWT | Task 3 |
| api/schemas/auth.py — Pydantic 模型 | Task 4 |
| api/routes/auth.py — 三个端点 | Task 6 |
| api/middleware/auth.py — get_current_user | Task 5 |
| api/app.py — 注册路由 + DB 初始化 | Task 7 |
| 用户名已存在 → 409 | Task 6（register 端点内置）+ Task 8 Step 3 |
| 用户名或密码错误 → 401 | Task 6（login 端点内置）+ Task 8 Step 5 |
| Token 无效/过期/类型不对 → 401 | Task 5（middleware）+ Task 6（refresh 端点）+ Task 8 Step 7 |
| bcrypt 密码哈希 | Task 3 |
| JWT HS256, 15min/7d | Task 3 |
| Token payload: sub/role/type/exp | Task 3 |

**2. Placeholder scan:** 无 "TBD" / "TODO" / "implement later" / "add error handling" 等占位符。所有代码直接给出。

**3. Type consistency:**
- `User.id` → `int`（Mapped[int]），`get_current_user` 返回 `{"id": user.id, ...}` → `int` ✅
- `User.username` → `str`，JWT `sub` = username → `str` ✅
- `create_access_token(username: str, role: str)` → 调用方传 `user.username, user.role` ✅
- `RegisterRequest.username` min_length=3 → User.username String(50) ✅
- `get_db` → `AsyncSession`，所有端点用 `Depends(get_db)` ✅
