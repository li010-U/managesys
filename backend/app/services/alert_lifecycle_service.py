# -*- coding: utf-8 -*-
"""告警生命周期引擎：自动恢复、去重防抖、偶发故障识别与记录。

确定性口径（与需求一致）：
- "已解决"：同一设备参数连续保持正常 >= ALERT_AUTO_RESOLVE_MINUTES 分钟，
  才将该设备告警标记为"已解决"；期间再次异常则不落地，继续挂起。
- 去重：以同一设备为去重维度，故障未解决期间不再产生重复告警。
- 短时自愈：故障在 ALERT_TRANSIENT_MAX_SECONDS 内恢复 => 偶发故障，
  入库记录(TransientFailureEvent)但不推送；随后按 30 分钟规则自动解决。
- 解决后可再次告警：进入"已解决"后再次异常允许再告警，
  但受 ALERT_COOLDOWN_MINUTES 冷却防抖约束。
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.timeutil import now_local
from app.db.retry import with_commit_retry
from app.models.alert import Alert, AlertAction
from app.models.env_weather import TransientFailureEvent

logger = logging.getLogger("managesys.alert_lifecycle")

_OPEN = ("new", "acknowledged")


class AlertLifecycleService:
    def __init__(
        self,
        db: AsyncSession,
        auto_resolve_minutes: Optional[int] = None,
        transient_max_seconds: Optional[int] = None,
        cooldown_minutes: Optional[int] = None,
    ):
        self.db = db
        self.auto_resolve_minutes = auto_resolve_minutes if auto_resolve_minutes is not None else settings.ALERT_AUTO_RESOLVE_MINUTES
        self.transient_max_seconds = transient_max_seconds if transient_max_seconds is not None else settings.ALERT_TRANSIENT_MAX_SECONDS
        self.cooldown_minutes = cooldown_minutes if cooldown_minutes is not None else settings.ALERT_COOLDOWN_MINUTES

    # ---------- 查询 --------------
    async def _find_open_by_device(self, target_type: str, target_id: str) -> Optional[Alert]:
        res = await self.db.execute(
            select(Alert).where(
                Alert.target_type == target_type,
                Alert.target_id == target_id,
                Alert.status.in_(_OPEN),
            ).order_by(Alert.created_at.asc()).limit(1)
        )
        return res.scalar_one_or_none()

    async def _find_recent_resolved(self, target_type: str, target_id: str) -> Optional[Alert]:
        res = await self.db.execute(
            select(Alert).where(
                Alert.target_type == target_type,
                Alert.target_id == target_id,
                Alert.status == "resolved",
            ).order_by(Alert.resolved_at.desc()).limit(1)
        )
        return res.scalar_one_or_none()

    # ---------- 信号入口 --------------
    async def register_signal(
        self,
        target_type: str,
        target_id: str,
        is_abnormal: bool,
        *,
        title: Optional[str] = None,
        level: str = "general",
        device_id: Optional[int] = None,
        metric: Optional[str] = None,
        source: str = "monitor",
        observed_at: Optional[datetime] = None,
    ) -> Dict[str, object]:
        """设备参数状态信号的统一入口。

        返回 {action, alert_id, status, transient, ...}，action 取值：
        - created: 新建告警
        - suppressed_cooldown: 冷却期内被防抖抑制
        - updated: 去重归并到既有开放告警（更新最近异常时间）
        - recovered: 恢复正常已记录
        - transient_created: 短时自愈，登记偶发故障
        - nothing: 无变化
        """
        observed_at = observed_at or now_local()
        result: Dict[str, object] = {"action": "nothing", "transient": False}
        open_alert = await self._find_open_by_device(target_type, str(target_id))

        if not is_abnormal:
            # ===== 恢复正常信号 =====
            if open_alert is None:
                return result
            await self._on_normal(open_alert, observed_at, result)
            await with_commit_retry(self.db.commit)
            return result

        # ===== 异常信号 =====
        if open_alert is not None:
            # 去重：故障未解决期间同一设备不再产生重复告警，仅刷新最近异常时间
            open_alert.last_abnormal_at = observed_at
            open_alert.status = "new"
            open_alert.occurrences = (open_alert.occurrences or 1) + 1
            result.update({"action": "updated", "alert_id": open_alert.id, "status": open_alert.status})
            await with_commit_retry(self.db.commit)
            return result

        # 无开放告警：冷却防抖检查（同一设备已解决后需冷却）
        recent = await self._find_recent_resolved(target_type, str(target_id))
        if recent is not None and recent.resolved_at is not None:
            cooldown_until = recent.resolved_at + timedelta(minutes=self.cooldown_minutes)
            if cooldown_until > observed_at:
                recent.cooldown_until = cooldown_until
                result.update({
                    "action": "suppressed_cooldown",
                    "alert_id": recent.id,
                    "status": recent.status,
                    "cooldown_until": cooldown_until,
                })
                await with_commit_retry(self.db.commit)
                return result

        # 新建告警
        alert = Alert(
            alert_rule_id=None,
            device_id=device_id,
            target_type=target_type,
            target_id=str(target_id),
            title=title or f"{target_type}:{target_id} 异常",
            level=level,
            status="new",
            source=source,
            created_at=observed_at,
            first_seen_at=observed_at,
            last_abnormal_at=observed_at,
            normal_since_at=None,
            auto_resolve_minutes=self.auto_resolve_minutes,
            dedupe_key=f"{target_type}|{target_id}",
            occurrences=1,
        )
        self.db.add(alert)
        await self.db.flush()
        result.update({"action": "created", "alert_id": alert.id, "status": alert.status})
        await with_commit_retry(self.db.commit)
        return result

    async def _on_normal(self, alert: Alert, observed_at: datetime, result: Dict[str, object]) -> None:
        """设备恢复正常：记录恢复时间；若为短时自愈则登记偶发。"""
        first = alert.first_seen_at or alert.created_at
        elapsed = 0.0
        if first is not None:
            elapsed = (observed_at - first).total_seconds()

        # 持续异常：30 分钟内再次异常则不落地（normal_since_at 不会置为恢复）
        # 这里仅处理"到达恢复信号"；若已在异常中，normal_since_at 在异常更新时被清空过。
        alert.normal_since_at = observed_at

        if not alert.is_transient and 0 < elapsed <= self.transient_max_seconds:
            # 短时自愈：偶发故障，只记录不推送
            alert.is_transient = True
            alert.lifecycle_action = "transient"
            alert.duration_seconds = int(elapsed)
            result.update({
                "action": "transient_created",
                "alert_id": alert.id,
                "status": alert.status,
                "transient": True,
                "duration_seconds": int(elapsed),
            })
            await self._ensure_transient_event(alert, observed_at, int(elapsed))
        else:
            result.update({"action": "recovered", "alert_id": alert.id, "status": alert.status})

    async def _ensure_transient_event(self, alert: Alert, recovered_at: datetime, duration: int) -> None:
        """登记偶发故障事件（幂等：同 alert_id 只登记一次）。"""
        if alert.id is None:
            return
        dup = (await self.db.execute(
            select(TransientFailureEvent.id).where(TransientFailureEvent.alert_id == alert.id).limit(1)
        )).scalar_one_or_none()
        if dup is not None:
            return
        event = TransientFailureEvent(
            alert_id=alert.id,
            target_type=alert.target_type,
            target_id=alert.target_id,
            metric=None,
            title=alert.title or "偶发故障",
            started_at=alert.first_seen_at or alert.created_at,
            recovered_at=recovered_at,
            duration_seconds=duration,
        )
        self.db.add(event)

    # ---------- 自动恢复扫描 --------------
    async def sweep_auto_resolve(self) -> List[int]:
        """扫描开放告警：参数连续正常 >= auto_resolve_minutes 后自动标记"已解决"。"""
        now = now_local()
        cutoff = now - timedelta(minutes=self.auto_resolve_minutes)
        rows = (await self.db.execute(
            select(Alert).where(
                Alert.status.in_(_OPEN),
                Alert.normal_since_at.isnot(None),
                Alert.normal_since_at <= cutoff,
            )
        )).scalars().all()

        resolved_ids: List[int] = []
        for a in rows:
            a.status = "resolved"
            a.resolved_at = now
            a.lifecycle_action = "auto_resolve"
            a.cooldown_until = now + timedelta(minutes=self.cooldown_minutes)
            start = a.last_abnormal_at or a.first_seen_at or a.created_at
            if start is not None:
                a.duration_seconds = max(0, int((now - start).total_seconds()))
            resolved_ids.append(a.id)
            if a.is_transient:
                await self._finalize_transient_event(a, now)

        if resolved_ids:
            await with_commit_retry(self.db.commit)
        return resolved_ids

    async def _finalize_transient_event(self, alert: Alert, resolved_at: datetime) -> None:
        event = (await self.db.execute(
            select(TransientFailureEvent).where(TransientFailureEvent.alert_id == alert.id).limit(1)
        )).scalar_one_or_none()
        if event is not None:
            event.recovered_at = resolved_at
            event.duration_seconds = alert.duration_seconds or event.duration_seconds
# ---------- 设备生命周期联动 ----------
    async def resolve_open_for_device(
        self,
        device_id: int,
        reason: str,
        operator: Optional[str] = None,
        note: Optional[str] = None,
    ) -> List[int]:
        """设备生命周期联动（下架/报废/删除/离线）时，一次性关闭该设备的未解决告警。

        与传感器驱动的"连续正常 30 分钟自动恢复"不同，这是设备侧确定性的状态联动：
        设备已不在役/已删除，其挂起告警已无意义，直接置为"已解决"并写入处理留痕。
        """
        now = now_local()
        rows = (await self.db.execute(
            select(Alert).where(
                Alert.status.in_(_OPEN),
                (Alert.device_id == device_id) | (Alert.target_id == str(device_id)),
            )
        )).scalars().all()
        resolved_ids: List[int] = []
        for a in rows:
            a.status = "resolved"
            a.resolved_at = now
            a.lifecycle_action = reason
            a.cooldown_until = now + timedelta(minutes=self.cooldown_minutes)
            start = a.last_abnormal_at or a.first_seen_at or a.created_at
            if start is not None:
                a.duration_seconds = max(0, int((now - start).total_seconds()))
            resolved_ids.append(a.id)
            self.db.add(AlertAction(
                alert_id=a.id,
                action_type="resolve",
                operator=operator,
                remark=note or ("设备状态联动: " + reason),
            ))
        if resolved_ids:
            await with_commit_retry(self.db.commit)
        return resolved_ids
