"""认证服务：注册、登录、密码管理"""
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.models.role import Role
from app.models.login_log import LoginLog
from app.schemas.auth import RegisterRequest


def validate_password_strength(password: str) -> tuple[bool, str]:
    """校验密码复杂度"""
    if len(password) < 8:
        return False, "密码长度不能少于8位"
    if not re.search(r"[a-zA-Z]", password):
        return False, "密码必须包含字母"
    if not re.search(r"[0-9]", password):
        return False, "密码必须包含数字"
    return True, ""


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _record_login_log(
        self, username: str, ip_address: Optional[str], status: str, reason: Optional[str] = None
    ):
        """记录登录日志"""
        log = LoginLog(
            username=username,
            ip_address=ip_address,
            login_status=status,
            fail_reason=reason,
        )
        self.db.add(log)
        await self.db.flush()

    async def register(self, req: RegisterRequest) -> User:
        """用户注册"""
        # 密码强度校验
        valid, msg = validate_password_strength(req.password)
        if not valid:
            raise ValueError(msg)

        # 检查用户名是否已存在
        result = await self.db.execute(select(User).where(User.username == req.username))
        if result.scalar_one_or_none():
            raise ValueError("用户名已存在")

        # 检查邮箱是否已存在
        if req.email:
            result = await self.db.execute(select(User).where(User.email == req.email))
            if result.scalar_one_or_none():
                raise ValueError("邮箱已被使用")

        # 创建用户
        user = User(
            username=req.username,
            real_name=req.real_name,
            email=req.email,
            phone=req.phone,
            department=req.department,
            hashed_password=hash_password(req.password),
            is_active=True,
        )

        # 新用户默认赋予"值班人员"角色
        result = await self.db.execute(select(Role).where(Role.code == "operator"))
        default_role = result.scalar_one_or_none()
        if default_role:
            user.roles = [default_role]

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def login(
        self, username: str, password: str, ip_address: Optional[str] = None
    ) -> tuple[str, User]:
        """用户登录，返回 (token, user)"""
        result = await self.db.execute(select(User).where(User.username == username))
        user = result.scalar_one_or_none()

        if not user:
            await self._record_login_log(username, ip_address, "fail", "用户不存在")
            raise ValueError("用户名或密码错误")

        # 检查账户是否锁定
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            remaining = (user.locked_until - datetime.now(timezone.utc)).seconds // 60
            await self._record_login_log(username, ip_address, "fail", "账户已锁定")
            raise ValueError(f"账户已被锁定，请{remaining}分钟后重试")

        # 检查账户是否停用
        if not user.is_active:
            await self._record_login_log(username, ip_address, "fail", "账户已停用")
            raise ValueError("账户已被停用，请联系管理员")

        # 验证密码
        if not verify_password(password, user.hashed_password):
            user.login_attempts += 1
            if user.login_attempts >= settings.LOGIN_MAX_ATTEMPTS:
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.LOGIN_LOCK_MINUTES
                )
            await self.db.flush()
            await self._record_login_log(username, ip_address, "fail", "密码错误")
            raise ValueError("用户名或密码错误")

        # 登录成功，重置失败次数
        user.login_attempts = 0
        user.locked_until = None
        user.last_login = datetime.now(timezone.utc)
        await self.db.flush()

        # 生成JWT
        token = create_access_token(data={"sub": str(user.id)})
        await self._record_login_log(username, ip_address, "success")
        return token, user

    async def change_password(self, user_id: int, old_password: str, new_password: str) -> None:
        """修改密码"""
        # 新密码强度校验
        valid, msg = validate_password_strength(new_password)
        if not valid:
            raise ValueError(msg)

        # 检查新旧密码不能相同
        if old_password == new_password:
            raise ValueError("新密码不能与旧密码相同")

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise ValueError("用户不存在")
        if not verify_password(old_password, user.hashed_password):
            raise ValueError("原密码错误")
        user.hashed_password = hash_password(new_password)
        await self.db.flush()
