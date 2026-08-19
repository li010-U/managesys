# -*- coding: utf-8 -*-
"""安全工具：密码哈希、JWT 令牌生成与验证。"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """对密码进行哈希处理"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码与哈希值是否匹配"""
    return pwd_context.verify(plain_password, hashed_password)


def _sign_token(data: dict, expires_delta, token_version: int, token_type: str) -> str:
    import uuid
    to_encode = dict(data)
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": uuid.uuid4().hex,
        "type": token_type,
        "ver": token_version,
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    token_version: int = 0,
) -> str:
    """创建 JWT 访问令牌（短寿命）。

    - 嵌入 token_version (ver)：修改密码/注销后递增，使旧令牌失效（会话作废）。
    - 嵌入 jti/type：令牌唯一标识与用途，供登出/刷新与审计追踪。
    """
    return _sign_token(data, expires_delta, token_version, "access")


def decode_access_token(token: str) -> Optional[dict]:
    """解码 JWT 令牌，失败/过期返回 None。"""
    try:
        return jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError:
        return None


def create_refresh_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
    token_version: int = 0,
) -> str:
    """Create a long-lived refresh token used only to mint new access tokens.

    Bound to the same sub/ver as the access token: bumping token_version on
    password change or logout invalidates already-issued refresh tokens too.
    """
    delta = expires_delta or timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES)
    return _sign_token(data, delta, token_version, "refresh")


def is_refresh_token(payload) -> bool:
    """Return True if the decoded payload is a refresh token."""
    return bool(payload) and payload.get("type") == "refresh"

