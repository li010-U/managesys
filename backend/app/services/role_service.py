"""角色管理服务"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.role import Role
from app.models.permission import Permission
from app.schemas.role import RoleCreateRequest, RoleUpdateRequest


class RoleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_roles(self) -> list[Role]:
        """获取所有角色"""
        result = await self.db.execute(select(Role).order_by(Role.id))
        return list(result.scalars().all())

    async def get_role_by_id(self, role_id: int) -> Role | None:
        """根据ID获取角色"""
        result = await self.db.execute(select(Role).where(Role.id == role_id))
        return result.scalar_one_or_none()

    async def create_role(self, req: RoleCreateRequest, operator_username: str = None, operator_ip: str = None) -> Role:
        """创建角色"""
        result = await self.db.execute(select(Role).where(Role.code == req.code))
        if result.scalar_one_or_none():
            raise ValueError("角色编码已存在")

        role = Role(
            name=req.name,
            code=req.code,
            description=req.description,
        )

        if req.permissions:
            result = await self.db.execute(select(Permission).where(Permission.id.in_(req.permissions)))
            role.permissions = list(result.scalars().all())

        self.db.add(role)
        await self.db.flush()
        await self.db.refresh(role)

        # 审计日志
        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="create",
            target_type="role",
            target_id=str(role.id),
            detail=f"创建角色: {role.name} ({role.code})",
            ip_address=operator_ip,
        )

        return role

    async def update_role(self, role_id: int, req: RoleUpdateRequest, operator_username: str = None, operator_ip: str = None) -> Role | None:
        """更新角色"""
        role = await self.get_role_by_id(role_id)
        if not role:
            return None
        if role.is_builtin:
            raise ValueError("内置角色不可修改")

        update_data = req.model_dump(exclude_unset=True, exclude={"permissions"})
        for field, value in update_data.items():
            setattr(role, field, value)

        if req.permissions is not None:
            result = await self.db.execute(select(Permission).where(Permission.id.in_(req.permissions)))
            role.permissions = list(result.scalars().all())

        await self.db.flush()
        await self.db.refresh(role)

        # 审计日志
        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="update",
            target_type="role",
            target_id=str(role.id),
            detail=f"更新角色: {role.name}",
            ip_address=operator_ip,
        )

        return role

    async def delete_role(self, role_id: int, operator_username: str = None, operator_ip: str = None) -> bool:
        """删除角色"""
        role = await self.get_role_by_id(role_id)
        if not role:
            return False
        if role.is_builtin:
            raise ValueError("内置角色不可删除")
        
        role_name = role.name
        await self.db.delete(role)
        await self.db.flush()

        # 审计日志
        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="delete",
            target_type="role",
            target_id=str(role_id),
            detail=f"删除角色: {role_name}",
            ip_address=operator_ip,
        )

        return True
