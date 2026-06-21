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
