"""告警 Service"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from app.models.alert import AlertRule, Alert, AlertAction

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
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def update(self, id: int, data):
        obj = await self.get_by_id(id)
        if not obj:
            return None
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(obj, k, v)
        await self.db.commit()
        await self.db.refresh(obj)
        return obj

    async def delete(self, id: int):
        obj = await self.get_by_id(id)
        if not obj:
            return False
        await self.db.delete(obj)
        await self.db.commit()
        return True


class AlertService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_list(self, page: int, page_size: int, keyword: str = None, level: str = None, status: str = None, target_type: str = None):
        q = select(Alert).options()
        if keyword:
            q = q.where(or_(Alert.title.ilike(f"%{keyword}%"), Alert.description.ilike(f"%{keyword}%")))
        if level:
            q = q.where(Alert.level == level)
        if status:
            q = q.where(Alert.status == status)
        if target_type:
            q = q.where(Alert.target_type == target_type)
        q = q.order_by(desc(Alert.created_at))
        total = (await self.db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
        q = q.offset((page - 1) * page_size).limit(page_size)
        items = (await self.db.execute(q)).scalars().all()
        return items, total

    async def get_by_id(self, id: int):
        result = await self.db.execute(select(Alert).where(Alert.id == id))
        return result.scalar_one_or_none()

    async def create(self, data: dict):
        obj = Alert(**data)
        self.db.add(obj)
        await self.db.commit()
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
        await self.db.commit()
        await self.db.refresh(alert)
        return alert

    async def get_stats(self):
        total = (await self.db.execute(select(func.count()).select_from(Alert))).scalar() or 0
        new_count = (await self.db.execute(select(func.count()).select_from(Alert).where(Alert.status == "new"))).scalar() or 0
        acknowledged = (await self.db.execute(select(func.count()).select_from(Alert).where(Alert.status == "acknowledged"))).scalar() or 0
        resolved = (await self.db.execute(select(func.count()).select_from(Alert).where(Alert.status == "resolved"))).scalar() or 0
        ignored = (await self.db.execute(select(func.count()).select_from(Alert).where(Alert.status == "ignored"))).scalar() or 0
        return {"total": total, "new": new_count, "acknowledged": acknowledged, "resolved": resolved, "ignored": ignored}
