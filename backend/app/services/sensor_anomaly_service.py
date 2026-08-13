# -*- coding: utf-8 -*-
"""传感器"两采集点之间越阈但采集点正常"的异常留痕 与 数据保留清理服务。

- reconcile_from_alerts: 以传感器告警为外部越阈信号，判定其是否落在两个正常采集点之间，
  若是则写入独立表 sensor_anomaly_gap（与 alerts 互补，不重复告警）。
- run_retention: 按 DATA_RETENTION_DAYS 滚动清理 sensor_data 与 sensor_anomaly_gap。
"""
from datetime import datetime, timedelta, timezone
from app.core.timeutil import ensure_utc
from typing import Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.retry import with_commit_retry
from app.models.alert import Alert
from app.models.sensor import Sensor, SensorData, SensorAnomalyGap


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    """统一时区规范（委托 timeutil.ensure_utc）"""
    return ensure_utc(dt)


class SensorAnomalyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    def _sensor_id_from_alert(self, alert: Alert) -> Optional[int]:
        if alert.target_type != "sensor":
            return None
        try:
            return int(alert.target_id)
        except (TypeError, ValueError):
            return None

    async def _bracketing_samples(self, sensor_id: int, ts: datetime):
        """返回 alert 时刻 ts 前后（按 recorded_at）紧邻的两个采集点。"""
        res = await self.db.execute(
            select(SensorData)
            .where(SensorData.sensor_id == sensor_id, SensorData.recorded_at <= ts)
            .order_by(SensorData.recorded_at.desc())
            .limit(1)
        )
        prev = res.scalar_one_or_none()
        res = await self.db.execute(
            select(SensorData)
            .where(SensorData.sensor_id == sensor_id, SensorData.recorded_at > ts)
            .order_by(SensorData.recorded_at.asc())
            .limit(1)
        )
        nxt = res.scalar_one_or_none()
        return prev, nxt

    @staticmethod
    def _is_normal_sample(sample: Optional[SensorData], sensor: Sensor) -> bool:
        """判定某采集点是否"正常"（未被标记异常，且不越阈）。"""
        if sample is None:
            return False
        if sample.source_mark and sample.source_mark != "normal":
            return False
        if sensor.threshold_min is not None and sample.value < sensor.threshold_min:
            return False
        if sensor.threshold_max is not None and sample.value > sensor.threshold_max:
            return False
        return True

    async def reconcile_from_alerts(self, since: Optional[datetime] = None) -> int:
        """以传感器告警为信号，补记"两采集点之间越阈但采集点正常"的留痕。

        返回本次新增留痕条数；按 alert_id 幂等去重。
        """
        threshold = settings.SENSOR_EXPECTED_INTERVAL_SECONDS * settings.SENSOR_GAP_TOLERANCE
        since = since or (datetime.now(timezone.utc) - timedelta(hours=24))

        result = await self.db.execute(
            select(Alert).where(
                Alert.target_type == "sensor",
                Alert.source.in_(["sensor", "monitor"]),
                Alert.created_at >= since,
            ).order_by(Alert.created_at.asc())
        )
        alerts = list(result.scalars().all())
        added = 0
        for alert in alerts:
            sensor_id = self._sensor_id_from_alert(alert)
            if sensor_id is None:
                continue
            dup = await self.db.execute(
                select(SensorAnomalyGap.id).where(SensorAnomalyGap.alert_id == alert.id).limit(1)
            )
            if dup.scalar_one_or_none() is not None:
                continue

            sensor = (await self.db.execute(
                select(Sensor).where(Sensor.id == sensor_id)
            )).scalar_one_or_none()
            if sensor is None:
                continue
            ts = _utc(alert.created_at) or datetime.now(timezone.utc)
            prev, nxt = await self._bracketing_samples(sensor_id, ts)
            prev_dt = _utc(prev.recorded_at) if prev else None
            nxt_dt = _utc(nxt.recorded_at) if nxt else None
            # 仅在两个采集点都正常（本次口径：至少前一采集点正常）时视为"采集点正常、之间越阈"
            if not self._is_normal_sample(prev, sensor):
                continue
            # 判定预警时刻与最近正常采集点相距超过一个间隔容差 => 落在"非采集点"窗口
            if prev_dt is None:
                in_gap = True
            else:
                in_gap = (ts - prev_dt).total_seconds() > threshold
            if not in_gap:
                continue
            gap = SensorAnomalyGap(
                sensor_id=sensor_id,
                alert_id=alert.id,
                detected_at=ts,
                window_start=prev_dt,
                window_end=nxt_dt,
                anomaly_type="between_points_breach",
                severity=alert.level if alert.level in ("info", "warning", "emergency") else "warning",
                remark=alert.title or "两采集点之间越阈（采集点体现正常）",
            )
            self.db.add(gap)
            added += 1
        if added:
            await with_commit_retry(self.db.commit)
        return added

    async def run_retention(self, days: Optional[int] = None) -> dict:
        """滚动清理超期数据。

        实际保留时长 = days + BUFFER，避免时区/边界误删刚满保留期的记录。
        """
        days = days or settings.DATA_RETENTION_DAYS
        buffer_days = settings.DATA_RETENTION_BUFFER_DAYS
        cutoff = datetime.now(timezone.utc) - timedelta(days=days + buffer_days)

        sd_res = await self.db.execute(
            delete(SensorData).where(SensorData.recorded_at < cutoff)
        )
        ag_res = await self.db.execute(
            delete(SensorAnomalyGap).where(SensorAnomalyGap.detected_at < cutoff)
        )
        await with_commit_retry(self.db.commit)
        return {
            "days": days,
            "buffer_days": buffer_days,
            "cutoff": cutoff.isoformat(),
            "sensor_data_deleted": sd_res.rowcount,
            "anomaly_gap_deleted": ag_res.rowcount,
        }
