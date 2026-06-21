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
