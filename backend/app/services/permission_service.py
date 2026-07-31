"""权限服务"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.permission import Permission


class PermissionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_permissions(self) -> list[Permission]:
        """获取所有权限"""
        result = await self.db.execute(select(Permission).order_by(Permission.module, Permission.id))
        return list(result.scalars().all())

    async def get_permissions_by_module(self, module: str) -> list[Permission]:
        """按模块获取权限"""
        result = await self.db.execute(
            select(Permission).where(Permission.module == module).order_by(Permission.id)
        )
        return list(result.scalars().all())
