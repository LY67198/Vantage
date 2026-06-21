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
