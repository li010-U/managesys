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

        # ==== 保留至少一个超级管理员 ====
        # 判断目标对象当前是否仍为超级管理员
        target_super = bool(user.is_super_admin) or any(getattr(r, "code", None) == "super_admin" for r in user.roles)
        if target_super:
            # 若 roles 被替换且不再包含 super_admin，或停用，均视为“移除超管”
            removing = bool(req.is_active is False)
            if req.roles is not None:
                new_role_ids = set(req.roles)
                keep_super_role = any(
                    getattr(r, "code", None) == "super_admin" and r.id in new_role_ids
                    for r in user.roles
                )
                if not keep_super_role:
                    removing = True
            if removing:
                # 超管自锁保护：禁止操作导致系统中无超级管理员
                from sqlalchemy import or_
                sa_roles = (await self.db.execute(
                    select(Role).where(Role.code == "super_admin")
                )).scalar_one_or_none()
                others = 0
                if sa_roles is not None:
                    from app.models.user import user_roles
                    other_ids = (await self.db.execute(
                        select(user_roles.c.user_id).where(user_roles.c.role_id == sa_roles.id)
                    )).scalars().all()
                    for oid in set(other_ids):
                        if oid == user_id:
                            continue
                        o = await self.get_user_by_id(oid)
                        if o and o.is_active and (o.is_super_admin or any(getattr(r, "code", None) == "super_admin" for r in o.roles)):
                            others += 1
                if others == 0:
                    raise ValueError("无法移除最后一个有效超级管理员，请先留下其他超管再操作")

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
