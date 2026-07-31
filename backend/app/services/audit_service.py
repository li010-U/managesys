"""审计日志服务"""
from datetime import datetime
from typing import Optional

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


class AuditService:
    """审计日志服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def log(
        db: AsyncSession,
        username: str,
        action: str,
        target_type: str,
        user_id: Optional[int] = None,
        target_id: Optional[str] = None,
        detail: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """记录审计日志（同步创建）"""
        audit_log = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=ip_address,
        )
        db.add(audit_log)
        return audit_log

    async def get_audit_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> tuple[list[AuditLog], int]:
        """获取审计日志列表（分页+多条件筛选）"""
        conditions = []

        if keyword:
            conditions.append(
                or_(
                    AuditLog.username.ilike(f"%{keyword}%"),
                    AuditLog.detail.ilike(f"%{keyword}%"),
                )
            )

        if action:
            conditions.append(AuditLog.action == action)

        if target_type:
            conditions.append(AuditLog.target_type == target_type)

        if start_date:
            conditions.append(AuditLog.created_at >= start_date)

        if end_date:
            conditions.append(AuditLog.created_at <= end_date)

        # 构建查询
        query = select(AuditLog)
        count_query = select(func.count(AuditLog.id))

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        # 获取总数
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # 分页查询
        query = query.order_by(AuditLog.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.db.execute(query)
        logs = list(result.scalars().all())

        return logs, total

    async def get_audit_log_by_id(self, log_id: int) -> AuditLog | None:
        """根据ID获取审计日志"""
        result = await self.db.execute(select(AuditLog).where(AuditLog.id == log_id))
        return result.scalar_one_or_none()
