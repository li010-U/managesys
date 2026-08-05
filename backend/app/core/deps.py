"""依赖注入：数据库会话、当前用户"""
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.security import decode_access_token
from app.db.retry import with_commit_retry
from app.db.session import async_session_factory
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_db(request: Request = None) -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话（支持并发安全的事务管理）"""
    async with async_session_factory() as session:
        try:
            yield session
            # ORM 写操作经常先 flush() 再依赖本处自动提交；
            # 但 flush 后对象已不在 session.new/dirty 中，
            # 仅判断 new/dirty/deleted 会导致写入被静默回滚（严重 bug）。
            # 因此：改写请求（POST/PUT/PATCH/DELETE）统一提交，
            # 纯读请求仅在有待提交变更时提交，保证读并发不受写串行影响。
            method = request.method if request else "GET"
            if (session.new or session.dirty or session.deleted) or method in {"POST", "PUT", "PATCH", "DELETE"}:
                await with_commit_retry(session.commit)
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """获取当前登录用户"""
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
        )

    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被停用",
        )

    return user


def require_permission(permission_code: str):
    """权限检查依赖（装饰器工厂）"""
    async def permission_checker(
        current_user: User = Depends(get_current_user),
    ):
        if current_user.is_super_admin:
            return current_user

        user_permissions = set()
        for role in current_user.roles:
            for perm in role.permissions:
                user_permissions.add(perm.code)

        if permission_code not in user_permissions:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少权限: {permission_code}",
            )

        return current_user

    return permission_checker

def require_any_permission(*permission_codes):
    """Require the current user to hold at least one of the given permission codes."""
    async def permission_checker(
        current_user=Depends(get_current_user),
    ):
        if current_user.is_super_admin:
            return current_user
        user_permissions = set()
        for role in current_user.roles:
            for perm in role.permissions:
                user_permissions.add(perm.code)
        if not user_permissions.intersection(permission_codes):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="missing_permission:" + ",".join(permission_codes),
            )
        return current_user
    return permission_checker


def has_permission(current_user, permission_code) -> bool:
    """Return True if current_user holds permission_code (super_admin always True)."""
    if current_user.is_super_admin:
        return True
    for role in current_user.roles:
        for perm in role.permissions:
            if perm.code == permission_code:
                return True
    return False
