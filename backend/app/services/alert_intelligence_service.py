# -*- coding: utf-8 -*-
"""告警智能：收敛去重、根因关联、自动升级。

- converge: 同类(同 dedupe_key)未处理告警连续出现时，归并到代表告警并累计 occurrences，
  避免告警风暴刷屏；同时处理完成的告警记录 acknowledged_at/resolved_at。
- correlate_room: 将同一机房的多个环境/设备告警聚合成"主告警"，给出可能的根因链
  （如温度告警 -> 空调/水浸/门磁联动）。
- auto_escalate: 未确认的 emergency 告警超时自动升级(仍为 emergency，标记 escalated)，
  供"下一个告警"与值班升级。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from app.core.timeutil import ensure_utc
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.retry import with_commit_retry
from app.models.alert import Alert
from app.models.sensor import Sensor


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    """统一时区规范（委托 timeutil.ensure_utc）"""
    return ensure_utc(dt)


def _alert_dedupe_key(alert: Alert) -> str:
    target = alert.target_id or (str(alert.device_id) if alert.device_id else "system")
    title = (alert.title or "unknown")[:60]
    return f"{alert.target_type}|{target}|{title}"


class AlertIntelligenceService:
    def __init__(self, db: AsyncSession, escalate_after_minutes: int = 30, window_minutes: int = 60):
        self.db = db
        self.escalate_after_minutes = escalate_after_minutes
        self.window_minutes = window_minutes

    async def converge_new_alert(self, alert: Alert) -> Alert:
        """创建告警时调用：若同 dedupe_key 的开放告警存在则归并，否则初始化收敛字段。"""
        if alert.status not in ("new", "acknowledged"):
            return alert
        key = _alert_dedupe_key(alert)
        alert.dedupe_key = key
        alert.occurrences = 1
        alert.first_seen_at = _utc(alert.created_at) or datetime.now(timezone.utc)
        # 查找同 key 且仍开放(未解决/未忽略)的既有告警进行归并
        if alert.id is not None:
            existing = (await self.db.execute(
                select(Alert).where(
                    Alert.dedupe_key == key,
                    Alert.id != alert.id,
                    Alert.status.in_(["new", "acknowledged"]),
                ).order_by(Alert.created_at.asc()).limit(1)
            )).scalar_one_or_none()
        else:
            existing = None
        if existing is not None:
            existing.occurrences = (existing.occurrences or 1) + 1
            # 代表告警的级别升级到更高
            level_rank = {"general": 1, "serious": 2, "emergency": 3}
            if level_rank.get(alert.level, 0) > level_rank.get(existing.level, 0):
                existing.level = alert.level
            await with_commit_retry(self.db.commit)
            await self.db.refresh(existing)
            return existing
        await with_commit_retry(self.db.commit)
        await self.db.refresh(alert)
        return alert

    async def auto_escalate(self) -> List[int]:
        """扫描超时未确认的 emergency/new 告警，标记为自动升级。返回升级的告警 id。"""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=self.escalate_after_minutes)
        q = select(Alert).where(
            Alert.status == "new",
            Alert.level == "emergency",
            Alert.created_at <= cutoff,
            Alert.escalated_at.is_(None),
        )
        rows = (await self.db.execute(q)).scalars().all()
        ids: List[int] = []
        for a in rows:
            a.escalated_from = a.level
            a.escalated_at = now
            ids.append(a.id)
        if ids:
            await with_commit_retry(self.db.commit)
        return ids

    async def correlate_room(self, room_id: int) -> Dict[str, any]:
        """将同一机房近期开放告警聚类，输出可能的根因链与关联对象。"""
        alerts = (await self.db.execute(
            select(Alert).where(Alert.status.in_(["new", "acknowledged"])).order_by(Alert.created_at.desc()).limit(200)
        )).scalars().all()
        # 映射 sensor_id -> room_id
        sensor_ids = []
        for a in alerts:
            if a.target_type == "sensor":
                try:
                    sensor_ids.append(int(a.target_id))
                except (TypeError, ValueError):
                    pass
        room_sensor_ids = set()
        if sensor_ids:
            srows = (await self.db.execute(
                select(Sensor.id).where(Sensor.id.in_(sensor_ids), Sensor.room_id == room_id)
            )).scalars().all()
            room_sensor_ids = set(srows)

        in_room = []
        for a in alerts:
            if a.target_type == "sensor":
                try:
                    if int(a.target_id) in room_sensor_ids:
                        in_room.append(a)
                except (TypeError, ValueError):
                    pass
            elif a.target_type == "device" and a.device_id:
                droom = await self._device_room(a.device_id)
                if droom == room_id:
                    in_room.append(a)
            elif a.target_type == "system":
                in_room.append(a)

        by_level = {"emergency": [], "serious": [], "general": []}
        for a in in_room:
            by_level.setdefault(a.level, []).append(a)

        temp_alerts = [a for a in in_room if "温度" in (a.title or "") or "temperature" in (a.title or "").lower()]
        humidity_alerts = [a for a in in_room if "湿度" in (a.title or "") or "humidity" in (a.title or "").lower()]
        power_alerts = [a for a in in_room if "功率" in (a.title or "") or "用电" in (a.title or "")]
        root_cause_hint = None
        if temp_alerts and humidity_alerts:
            root_cause_hint = "温度与湿度同时异常，可能为空调/制冷故障或冷热通道异常"
        elif temp_alerts:
            root_cause_hint = "存在温度告警，建议检查空调制冷与冷通道气流"
        elif power_alerts:
            root_cause_hint = "存在功率/用电告警，建议检查供电负载与配电"

        return {
            "room_id": room_id,
            "active_alert_count": len(in_room),
            "by_level": {k: [{"id": a.id, "title": a.title, "level": a.level, "occurrences": a.occurrences} for a in v] for k, v in by_level.items()},
            "temperature_count": len(temp_alerts),
            "humidity_count": len(humidity_alerts),
            "power_count": len(power_alerts),
            "root_cause_hint": root_cause_hint,
        }

    async def _device_room(self, device_id: int) -> Optional[int]:
        from app.models.device import Device
        dev = (await self.db.get(Device, device_id))
        return dev.rack.room_id if dev and dev.rack else None