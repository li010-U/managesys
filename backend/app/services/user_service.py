"""用户管理服务"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserCreateRequest, UserUpdateRequest


class UserService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_users(self, page: int = 1, page_size: int = 10, keyword: str = None) -> tuple[list[User], int]:
        """获取用户列表（分页）"""
        query = select(User)
        count_query = select(func.count(User.id))

        if keyword:
            keyword_filter = User.username.ilike(f"%{keyword}%")
            query = query.where(keyword_filter)
            count_query = count_query.where(keyword_filter)

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(User.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        users = list(result.scalars().all())

        return users, total

    async def get_user_by_id(self, user_id: int) -> User | None:
        """根据ID获取用户"""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user(self, req: UserCreateRequest, operator_username: str = None, operator_ip: str = None) -> User:
        """创建用户"""
        result = await self.db.execute(select(User).where(User.username == req.username))
        if result.scalar_one_or_none():
            raise ValueError("用户名已存在")

        user = User(
            username=req.username,
            real_name=req.real_name,
            email=req.email,
            phone=req.phone,
            department=req.department,
            position=req.position,
            is_active=req.is_active,
            hashed_password=hash_password(req.password),
        )

        if req.roles:
            result = await self.db.execute(select(Role).where(Role.id.in_(req.roles)))
            user.roles = list(result.scalars().all())

        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        # 审计日志
        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or user.username,
            action="create",
            target_type="user",
            target_id=str(user.id),
            detail=f"创建用户: {user.username}",
            ip_address=operator_ip,
        )

        return user

    async def update_user(self, user_id: int, req: UserUpdateRequest, operator_username: str = None, operator_ip: str = None) -> User | None:
        """更新用户信息"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return None

        update_data = req.model_dump(exclude_unset=True, exclude={"roles"})
        old_values = {k: getattr(user, k) for k in update_data.keys()}

        for field, value in update_data.items():
            setattr(user, field, value)

        if req.roles is not None:
            result = await self.db.execute(select(Role).where(Role.id.in_(req.roles)))
            user.roles = list(result.scalars().all())

        await self.db.flush()
        await self.db.refresh(user)

        # 审计日志
        from app.services.audit_service import AuditService
        detail_parts = [f"更新用户 {user.username} 字段: "]
        for k, v in update_data.items():
            if old_values.get(k) != v:
                detail_parts.append(f"{k}: {old_values.get(k)} -> {v}")
        AuditService.log(
            self.db,
            username=operator_username or user.username,
            action="update",
            target_type="user",
            target_id=str(user.id),
            detail="".join(detail_parts) if len(detail_parts) > 1 else f"更新用户 {user.username}",
            ip_address=operator_ip,
        )

        return user

    async def delete_user(self, user_id: int, operator_username: str = None, operator_ip: str = None) -> bool:
        """删除用户（软删除：停用）"""
        user = await self.get_user_by_id(user_id)
        if not user:
            return False
        if user.is_super_admin:
            raise ValueError("不能删除超级管理员")
        user.is_active = False
        await self.db.flush()

        # 审计日志
        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or user.username,
            action="delete",
            target_type="user",
            target_id=str(user.id),
            detail=f"删除用户: {user.username}（软删除）",
            ip_address=operator_ip,
        )

        return True
