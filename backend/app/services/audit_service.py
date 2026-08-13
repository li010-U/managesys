"""审计日志服务"""
from datetime import datetime, date
from typing import Optional, Any

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
        request_path: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """记录审计日志（同步创建，随外层事务一起提交）"""
        audit_log = AuditLog(
            user_id=user_id,
            username=username or "system",
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=ip_address,
            request_path=request_path,
            user_agent=user_agent,
        )
        db.add(audit_log)
        return audit_log

    @staticmethod
    def log_request(
        db: AsyncSession,
        request: Any,
        current_user: Any = None,
        action: str = "update",
        target_type: str = "system",
        target_id: Optional[str] = None,
        detail: Optional[str] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Optional[AuditLog]:
        """从请求+操作者上下文创建审计日志（更省心的统一入口）。

        - 自动从 Request 提取 IP / 路径 / User-Agent；
        - username 优先取显式传入，其次取 current_user.username，最后 system。
        - 需要外层事务提交（由 get_db 依赖统一 commit）。
        """
        try:
            from app.core.iputils import get_client_ip
            if ip_address is None and request is not None:
                ip_address = get_client_ip(
                    request.headers.get("X-Forwarded-For"),
                    request.headers.get("X-Real-IP"),
                    request.client.host if request.client else None,
                )
        except Exception:
            ip_address = ip_address or None

        request_path = None
        user_agent = None
        if request is not None:
            try:
                request_path = request.url.path[:256]
            except Exception:
                request_path = None
            try:
                user_agent = (request.headers.get("User-Agent") or "")[:512]
            except Exception:
                user_agent = None

        if username is None:
            username = getattr(current_user, "username", None) or "system"
        user_id = getattr(current_user, "id", None)

        return AuditService.log(
            db,
            username=username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=ip_address,
            request_path=request_path,
            user_agent=user_agent,
            user_id=user_id,
        )

    async def get_audit_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        keyword: Optional[str] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        username: Optional[str] = None,
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

        if username:
            conditions.append(AuditLog.username == username)

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

    async def summary(
        self,
        days: int = 7,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> dict:
        """审计统计：总数、按操作类型/对象类型/操作人数量，及近 N 天趋势。"""
        conditions = []
        if start_date:
            conditions.append(AuditLog.created_at >= start_date)
        if end_date:
            conditions.append(AuditLog.created_at <= end_date)

        base = and_(*conditions) if conditions else None

        async def _agg(col):
            q = select(col, func.count(AuditLog.id))
            if base is not None:
                q = q.where(base)
            q = q.group_by(col).order_by(func.count(AuditLog.id).desc())
            res = await self.db.execute(q.limit(20))
            return [{"name": k, "count": n} for k, n in res.all()]

        total_q = select(func.count(AuditLog.id))
        if base is not None:
            total_q = total_q.where(base)
        total = (await self.db.execute(total_q)).scalar() or 0

        action_stat = await _agg(AuditLog.action)
        target_stat = await _agg(AuditLog.target_type)
        user_stat = await _agg(AuditLog.username)

        # 近 N 天每日趋势（SQLite date() 截取日期）
        trend_conditions = []
        try:
            from datetime import timedelta
            since = (end_date or datetime.utcnow()) - timedelta(days=days - 1)
            trend_conditions.append(AuditLog.created_at >= since)
        except Exception:
            pass
        trend = []
        try:
            q = select(func.date(AuditLog.created_at), func.count(AuditLog.id))
            if trend_conditions:
                q = q.where(and_(*trend_conditions))
            q = q.group_by(func.date(AuditLog.created_at)).order_by(func.date(AuditLog.created_at))
            for d, n in (await self.db.execute(q)).all():
                trend.append({"date": str(d), "count": n})
        except Exception:
            trend = []

        return {
            "total": total,
            "by_action": action_stat,
            "by_target": target_stat,
            "by_user": user_stat,
            "trend": trend,
        }

    async def purge(self, before: datetime) -> int:
        """删除指定时间之前的历史审计日志，返回删除条数（保留策略）。"""
        from sqlalchemy import delete
        res = await self.db.execute(delete(AuditLog).where(AuditLog.created_at < before))
        return res.rowcount or 0

    async def export_all(
        self,
        keyword: Optional[str] = None,
        action: Optional[str] = None,
        target_type: Optional[str] = None,
        username: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100000,
    ) -> list[AuditLog]:
        """导出全部符合条件的审计日志（不分页，最多 limit 条）。"""
        conditions = []
        if keyword:
            conditions.append(or_(AuditLog.username.ilike(f"%{keyword}%"), AuditLog.detail.ilike(f"%{keyword}%")))
        if action:
            conditions.append(AuditLog.action == action)
        if target_type:
            conditions.append(AuditLog.target_type == target_type)
        if username:
            conditions.append(AuditLog.username == username)
        if start_date:
            conditions.append(AuditLog.created_at >= start_date)
        if end_date:
            conditions.append(AuditLog.created_at <= end_date)

        q = select(AuditLog)
        if conditions:
            q = q.where(and_(*conditions))
        q = q.order_by(AuditLog.created_at.desc()).limit(limit)
        res = await self.db.execute(q)
        return list(res.scalars().all())
