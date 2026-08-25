"""告警 Service"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, case
from app.models.alert import AlertRule, Alert, AlertAction
from app.db.retry import with_commit_retry

# 排序字段白名单（防任意列排序注入）
ALERT_SORT_WHITELIST = {
    "id": Alert.id, "title": Alert.title, "level": Alert.level, "status": Alert.status,
    "target_type": Alert.target_type, "source": Alert.source, "occurrences": Alert.occurrences,
    "created_at": Alert.created_at, "resolved_at": Alert.resolved_at,
}

class AlertRuleService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_list(self, page: int, page_size: int, keyword: str = None, enabled: bool = None):
        q = select(AlertRule)
        if keyword:
            q = q.where(or_(AlertRule.name.ilike(f"%{keyword}%"), AlertRule.code.ilike(f"%{keyword}%")))
        if enabled is not None:
            q = q.where(AlertRule.enabled == enabled)
        q = q.order_by(desc(AlertRule.created_at))
        total = (await self.db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        q = q.offset((page - 1) * page_size).limit(page_size)
        items = (await self.db.execute(q)).scalars().all()
        return items, total

    async def get_by_id(self, id: int):
        result = await self.db.execute(select(AlertRule).where(AlertRule.id == id))
        return result.scalar_one_or_none()

    async def create(self, data):
        obj = AlertRule(**data.model_dump())
        self.db.add(obj)
        await with_commit_retry(self.db.commit)
        await self.db.refresh(obj)
        return obj

    async def update(self, id: int, data):
        obj = await self.get_by_id(id)
        if not obj:
            return None
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(obj, k, v)
        await with_commit_retry(self.db.commit)
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: int):
        obj = await self.get_by_id(id)
        if not obj:
            return False
        await self.db.delete(obj)
        await with_commit_retry(self.db.commit)
        return True


class AlertService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_list(self, page: int, page_size: int, keyword: str = None, level: str = None, status: str = None, target_type: str = None, sort_by: str = None, order: str = "desc"):
        q = select(Alert).options()
        if keyword:
            q = q.where(or_(Alert.title.ilike(f"%{keyword}%"), Alert.description.ilike(f"%{keyword}%")))
        if level:
            q = q.where(Alert.level == level)
        if status:
            q = q.where(Alert.status == status)
        if target_type:
            q = q.where(Alert.target_type == target_type)
        status_order = case(
            (Alert.status == "new", 3),
            (Alert.status == "acknowledged", 2),
            (Alert.status == "resolved", 1),
            else_=0,
        )
        level_order = case(
            (Alert.level == "emergency", 3),
            (Alert.level == "serious", 2),
            (Alert.level == "general", 1),
            else_=0,
        )
        sort_col = ALERT_SORT_WHITELIST.get(sort_by)
        if sort_col is None:
            q = q.order_by(
                status_order.desc(),
                level_order.desc(),
                desc(Alert.created_at),
            )
        elif order and order.lower() == "asc":
            q = q.order_by(sort_col.asc(), Alert.id.desc())
        else:
            q = q.order_by(sort_col.desc(), Alert.id.desc())
        total = (await self.db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        q = q.offset((page - 1) * page_size).limit(page_size)
        items = (await self.db.execute(q)).scalars().all()
        return items, total

    async def get_by_id(self, id: int):
        result = await self.db.execute(select(Alert).where(Alert.id == id))
        return result.scalar_one_or_none()

    async def create(self, data: dict):
        # 仅接受显式白名单字段，避免未预期键注入模型属性
        allowed = {"alert_rule_id", "device_id", "target_type", "target_id", "title",
                   "description", "level", "status", "source", "dedupe_key"}
        obj = Alert(**{k: v for k, v in data.items() if k in allowed and v is not None})
        self.db.add(obj)
        await with_commit_retry(self.db.commit)
        await self.db.refresh(obj)
        return obj

    async def handle(self, id: int, data: dict, operator: str):
        alert = await self.get_by_id(id)
        if not alert:
            return None
        action = AlertAction(
            alert_id=alert.id,
            action_type=data["action_type"],
            operator=operator,
            remark=data.get("remark"),
            root_cause=data.get("root_cause"),
        )
        self.db.add(action)
        if data["action_type"] == "acknowledge":
            alert.status = "acknowledged"
        elif data["action_type"] == "resolve":
            alert.status = "resolved"
        elif data["action_type"] == "ignore":
            alert.status = "ignored"
        await with_commit_retry(self.db.commit)
        await self.db.refresh(alert)
        return alert

    async def get_stats(self):
        total = (await self.db.execute(select(func.count()).select_from(Alert))).scalar() or 0
        new_count = (await self.db.execute(select(func.count()).select_from(Alert).where(Alert.status == "new"))).scalar() or 0
        acknowledged = (await self.db.execute(select(func.count()).select_from(Alert).where(Alert.status == "acknowledged"))).scalar() or 0
        resolved = (await self.db.execute(select(func.count()).select_from(Alert).where(Alert.status == "resolved"))).scalar() or 0
        ignored = (await self.db.execute(select(func.count()).select_from(Alert).where(Alert.status == "ignored"))).scalar() or 0
        return {"total": total, "new": new_count, "acknowledged": acknowledged, "resolved": resolved, "ignored": ignored}

