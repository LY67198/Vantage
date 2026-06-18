# Day 32 JWT 鉴权 — 设计方案

**日期：** 2026-06-18
**状态：** 已确认

## 概述

为 Vantage API 添加用户认证体系：注册、登录、Token 刷新、请求鉴权。采用 JWT（HS256）+ bcrypt，Access Token 短有效（15min），Refresh Token 长有效（7d）。

## 技术选型

| 层 | 选型 | 理由 |
|---|---|---|
| JWT 编解码 | `python-jose` | FastAPI 官方推荐，HS256 简单可靠 |
| 密码哈希 | `bcrypt` | 已安装，自适应盐值，抗暴力破解 |
| ORM | `SQLAlchemy 2.0` | 声明式模型，与 PostgreSQL 对接 |
| Token 策略 | Access(15min) + Refresh(7d) | 短 access 降低泄漏风险，长 refresh 免频繁登录 |

## 新增文件（5 个）

```
api/schemas/auth.py      — RegisterRequest / LoginRequest / TokenResponse / RefreshRequest
api/routes/auth.py        — POST /auth/register, /auth/login, /auth/refresh
api/middleware/auth.py    — get_current_user 依赖（Bearer token → user dict）
models/__init__.py        — DeclarativeBase + engine（SQLAlchemy 2.0）
models/user.py            — User ORM 模型
services/auth_service.py  — 业务逻辑：hash_password / verify_password / create_token / decode_token / get_user_by_username / create_user
```

## 修改文件（1 个）

```
api/app.py — 注册 auth_router（prefix="/auth"）+ lifespan 中初始化 DB 引擎
```

> `/query` 端点鉴权暂不加 — 等中间件完成后统一在 Day 33b 或后续加上，保持 Day 32 改动聚焦。

## 数据流

```
注册: POST /auth/register → hash(password) → INSERT user → 返回 tokens
登录: POST /auth/login    → 查 user → verify(password) → 返回 tokens
刷新: POST /auth/refresh  → decode refresh_token → 查 user → 返回新 tokens
鉴权: Authorization: Bearer <token> → decode → 查 user → Depends 注入
```

## API 设计

| 端点 | 方法 | 鉴权 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/auth/register` | POST | 无 | `{username, password, email?}` | `{access_token, refresh_token, token_type}` |
| `/auth/login` | POST | 无 | `{username, password}` | `{access_token, refresh_token, token_type}` |
| `/auth/refresh` | POST | 无 | `{refresh_token}` | `{access_token, refresh_token}` |

## User 模型

```python
class User(Base):
    __tablename__ = "users"
    id: int (PK, auto)
    username: str (unique, indexed)
    password_hash: str
    email: str | None
    role: str (default="user")  # user / admin — RBAC 预留
    created_at: datetime
```

## JWT 配置

- 密钥：`SECRET_KEY`（从环境变量读取，默认 dev-secret）
- 算法：HS256
- Access token: 15 分钟
- Refresh token: 7 天
- Token payload: `{sub: username, role: role, type: "access"|"refresh", exp: ...}`

## 错误处理

| 场景 | HTTP | 响应 |
|------|------|------|
| 用户名已存在 | 409 | `{"detail": "用户名已存在"}` |
| 用户名或密码错误 | 401 | `{"detail": "用户名或密码错误"}` |
| Token 过期 | 401 | `{"detail": "Token 已过期，请刷新"}` |
| Token 无效 | 401 | `{"detail": "Token 无效"}` |
| Refresh token 类型不对 | 401 | `{"detail": "请使用 refresh token"}` |

## 实现顺序

1. `models/` — DeclarativeBase + engine + User 模型
2. `services/auth_service.py` — hash/verify + JWT 编解码
3. `api/schemas/auth.py` — Pydantic 模型
4. `api/routes/auth.py` — 三个端点
5. `api/middleware/auth.py` — get_current_user 依赖
6. `api/app.py` — 注册路由 + DB 初始化

## 不在范围内

- 前端登录页（Day 32 Vue 脚手架部分，另开设计）
- `/query` 端点强制鉴权（middleware 完成后自然接入）
- SQL Admin 管理面板
- OAuth / 第三方登录
- 邮箱验证
