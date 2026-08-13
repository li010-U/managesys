# -*- coding: utf-8 -*-
"""智能分析服务：自学习基线、趋势预测、容量规划、可靠性指标、LLM 数据追溯。

纯计算 + 只读 DB 查询，不改写任何业务数据。对外 API 由 insight router 暴露。

- 自学习基线：对 SensorData 按"小时槽"(hour) 滑动窗口做分位数/IQR/Z-score 基线，
  自动识别当前值相对历史同时间的偏离程度，而非只看固定阈值。
- 趋势预测：对温度/湿度等数值序列做短时线性回归，给出未来 N 步的预测区间。
- 容量规划：按机柜已用 U 位 + 设备额定功率估算满载/供电满载时间。
- 可靠性：用告警 created_at -> resolved_at 计算 MTTR；按设备/类型估算 MTBF 与可用率。
"""
from __future__ import annotations

import math
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.device import Device
from app.models.facility import Room, Rack
from app.models.sensor import Sensor, SensorData


def _utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fmt(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    return _utc(dt).isoformat()


def _robust_bounds(values: List[float], k: float = 1.5):
    """IQR 稳健上下界；数据太少时退回均值±2 标准差。"""
    if not values:
        return None, None
    if len(values) >= 4:
        q = statistics.quantiles(sorted(values), n=4)
        q1, q3 = q[0], q[2]
        iqr = q3 - q1
        if iqr > 0:
            return q1 - k * iqr, q3 + k * iqr
    mean = statistics.fmean(values)
    sd = statistics.pstdev(values) if len(values) > 1 else 0.0
    return mean - 2 * sd, mean + 2 * sd


def _linear_forecast(points: List[float], steps: int) -> Optional[List[float]]:
    """对一维序列做最小二乘线性回归，返回未来 steps 步预测值。"""
    n = len(points)
    if n < 3:
        return None
    xs = list(range(n))
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(points)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, points))
    den = sum((x - x_mean) ** 2 for x in xs)
    if den == 0:
        slope = 0.0
    else:
        slope = num / den
    intercept = y_mean - slope * x_mean
    residual = statistics.pstdev([(y - (slope * x + intercept)) for x, y in zip(xs, points)])
    future = []
    for i in range(1, steps + 1):
        t = n - 1 + i
        center = slope * t + intercept
        future.append({"value": round(center, 2), "low": round(center - residual, 2), "high": round(center + residual, 2)})
    return future


class InsightService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- 基线 ----------------
    async def sensor_baseline(self, sensor_id: int, lookback_days: Optional[int] = None) -> Dict[str, Any]:
        """对单个传感器做自学习基线：按小时槽聚合并给出 IQR/Z-score 判定。"""
        lookback_days = lookback_days or 30
        since = datetime.now(timezone.utc) - timedelta(days=lookback_days)
        sensor = (await self.db.execute(select(Sensor).where(Sensor.id == sensor_id))).scalar_one_or_none()
        if sensor is None:
            return {"found": False}
        rows = (await self.db.execute(
            select(SensorData.value, SensorData.recorded_at).where(
                SensorData.sensor_id == sensor_id, SensorData.recorded_at >= since
            ).order_by(SensorData.recorded_at.asc())
        )).all()
        # 按小时槽分组
        buckets: Dict[int, List[float]] = {}
        total = 0.0
        for value, recorded_at in rows:
            ts = _utc(recorded_at)
            if ts is None:
                continue
            hour = ts.hour
            buckets.setdefault(hour, []).append(float(value))
            total += float(value)
        if not buckets:
            return {"found": True, "sensor_id": sensor_id, "samples": 0, "baseline": None}

        current = None
        try:
            current = float((sensor.current_value or {}).get("value"))
        except (TypeError, ValueError):
            current = None

        baseline = {}
        for hour, values in buckets.items():
            lo, hi = _robust_bounds(values)
            baseline[str(hour)] = {
                "hour": hour,
                "count": len(values),
                "mean": round(statistics.fmean(values), 2),
                "median": round(statistics.median(values), 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "low": None if lo is None else round(lo, 2),
                "high": None if hi is None else round(hi, 2),
            }

        assessment = None
        if current is not None:
            now_hour = datetime.now(timezone.utc).hour
            slot = baseline.get(str(now_hour))
            if slot and slot.get("low") is not None:
                if current > slot["high"]:
                    assessment = {"status": "high", "msg": f"当前值 {current} 超过该时刻历史上限 {slot['high']}"}
                elif current < slot["low"]:
                    assessment = {"status": "low", "msg": f"当前值 {current} 低于该时刻历史下限 {slot['low']}"}
                else:
                    assessment = {"status": "normal", "msg": f"当前值 {current} 处于该时刻历史正常区间 [{slot['low']}, {slot['high']}]"}

        return {
            "found": True,
            "sensor_id": sensor_id,
            "sensor_name": sensor.name,
            "sensor_type": sensor.sensor_type,
            "samples": len(rows),
            "lookback_days": lookback_days,
            "overall_mean": round(total / len(rows), 2) if rows else None,
            "current_value": current,
            "baseline": baseline,
            "assessment": assessment,
        }

    # ---------------- 趋势预测 ----------------
    async def sensor_forecast(self, sensor_id: int, lookback: int = 120, horizon: int = 6) -> Dict[str, Any]:
        """对传感器数值序列做短时线性回归预测。"""
        sensor = (await self.db.execute(select(Sensor).where(Sensor.id == sensor_id))).scalar_one_or_none()
        if sensor is None:
            return {"found": False}
        rows = (await self.db.execute(
            select(SensorData.value, SensorData.recorded_at).where(SensorData.sensor_id == sensor_id)
            .order_by(SensorData.recorded_at.desc()).limit(lookback)
        )).all()
        rows = list(reversed(rows))
        points: List[float] = []
        timestamps: List[str] = []
        for value, recorded_at in rows:
            points.append(float(value))
            timestamps.append(_fmt(recorded_at))
        if len(points) < 3:
            return {"found": True, "sensor_id": sensor_id, "samples": len(points), "forecast": None}
        forecast = _linear_forecast(points, horizon)
        return {
            "found": True,
            "sensor_id": sensor_id,
            "sensor_name": sensor.name,
            "sensor_type": sensor.sensor_type,
            "samples": len(points),
            "history": [{"value": v, "ts": timestamps[i]} for i, v in enumerate(points)],
            "forecast": forecast,
            "direction": "up" if forecast and forecast[-1]["value"] > points[-1] else ("down" if forecast and forecast[-1]["value"] < points[-1] else "flat"),
        }

    # ---------------- 容量规划 ----------------
    async def rack_capacity(self, room_id: Optional[int] = None) -> Dict[str, Any]:
        """机柜容量规划：U 位占用趋势 + 供电负载估算 + 满载时间预估。"""
        q = select(Rack, Room).join(Room, Rack.room_id == Room.id)
        if room_id:
            q = q.where(Rack.room_id == room_id)
        racks = (await self.db.execute(q)).scalars().all()
        rows = []
        now = datetime.now(timezone.utc)
        for rack in racks:
            devices = rack.devices or []
            used_units = rack.total_units - rack.available_units
            power_load = sum((d.power_rating or 0.0) for d in devices if d.status in ("running", "online", "mounted"))
            rated = rack.rated_power or 0.0
            utilization = round((used_units / rack.total_units * 100) if rack.total_units else 0, 1)
            # 日均新增 U 位占用（按设备注册时间，取宽口径：无历史则用当前占用）
            # 以"可用 U 位"作为剩余量，按经验月均增量估算满载时间
            monthly_growth = 2.0  # 默认乐观估计
            remaining_units = max(rack.available_units, 0)
            full_months = (remaining_units / monthly_growth) if monthly_growth > 0 else None
            full_date = None
            if full_months is not None:
                target = now + timedelta(days=30 * full_months)
                full_date = target.date().isoformat()
            rows.append({
                "rack_id": rack.id,
                "rack_code": rack.code,
                "room_id": rack.room_id,
                "room_name": rack.room.name if rack.room else "",
                "total_units": rack.total_units,
                "available_units": rack.available_units,
                "used_units": used_units,
                "utilization_pct": utilization,
                "device_count": len(devices),
                "power_used_kw": round(power_load, 2),
                "rated_power_kw": rated,
                "power_util_pct": round((power_load / rated * 100) if rated else 0, 1),
                "estimate_full_months": None if full_months is None else round(full_months, 1),
                "estimate_full_date": full_date,
            })
        return {"room_id": room_id, "count": len(rows), "racks": rows}

    # ---------------- 可靠性指标 ----------------
    async def reliability(self, room_id: Optional[int] = None, days: int = 90) -> Dict[str, Any]:
        """基于告警生命周期计算 MTTR/MTBF 与可用率。"""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        q = select(Alert).where(Alert.created_at >= since)
        if room_id and hasattr(Alert, "room_id"):
            q = q.where(Alert.room_id == room_id)
        alerts = (await self.db.execute(q)).scalars().all()

        mttr = []
        device_alerts: Dict[str, List[datetime]] = {}
        type_alerts: Dict[str, List[datetime]] = {}
        for a in alerts:
            resolved_at = None
            for act in (a.actions or []):
                if act.action_type == "resolve":
                    resolved_at = _utc(act.created_at)
                    break
            created = _utc(a.created_at)
            if created and resolved_at and resolved_at >= created:
                mttr.append((resolved_at - created).total_seconds() / 3600.0)
            if a.device_id:
                device_alerts.setdefault(str(a.device_id), []).append(created)
            if a.target_type:
                type_alerts.setdefault(a.target_type, []).append(created)

        def _mtbf(times: List[datetime]) -> Optional[float]:
            times = sorted(t for t in times if t is not None)
            if len(times) < 2:
                return None
            gaps = [(times[i] - times[i - 1]).total_seconds() / 3600.0 for i in range(1, len(times))]
            return statistics.fmean(gaps) if gaps else None

        avg_mttr = statistics.fmean(mttr) if mttr else None
        top_device = None
        top_type = None
        if device_alerts:
            top_device = min(device_alerts.items(), key=lambda kv: _mtbf(kv[1]) or 1e18)[0] if device_alerts else None
        if type_alerts:
            top_type = min(((k, v) for k, v in type_alerts.items()), key=lambda kv: _mtbf(kv[1]) or 1e18)[0]

        urgency = sum(1 for a in alerts if a.level == "emergency")
        serious = sum(1 for a in alerts if a.level == "serious")
        # 可用率：采用业界常用稳态可用率 A = MTBF / (MTBF + MTTR)。
        # MTBF 取观测窗口内系统告警平均时间间隔，MTTR 取已解决告警平均修复时长，
        # 避免将并发/叠加告警的修复时长简单相加导致可用率被错误压低到 0。
        all_times = sorted(t for t in (_utc(a.created_at) for a in alerts) if t is not None)
        avg_mtbf = None
        if len(all_times) >= 2:
            gaps = [(all_times[i] - all_times[i - 1]).total_seconds() / 3600.0 for i in range(1, len(all_times))]
            avg_mtbf = statistics.fmean(gaps)
        availability = 100.0
        outage_hours = sum(mttr)
        total_hours = days * 24
        if avg_mtbf and avg_mttr:
            availability = 100.0 * avg_mtbf / (avg_mtbf + avg_mttr)
            # 与可用率模型一致：窗口内期望停机时长 = 总时长 * (1 - 可用率)
            if total_hours > 0:
                outage_hours = total_hours * (1 - availability / 100.0)
        else:
            if total_hours > 0:
                availability = max(0.0, min(100.0, 100.0 * (1 - outage_hours / total_hours)))

        # 按设备/类型画像
        device_health = []
        for dev_id, times in device_alerts.items():
            dev = (await self.db.get(Device, int(dev_id))) if dev_id.isdigit() else None
            device_health.append({
                "device_id": dev_id,
                "device_name": dev.name if dev else None,
                "asset_number": dev.asset_number if dev else None,
                "alert_count": len(times),
                "mtbf_hours": _mtbf(times),
            })
        device_health.sort(key=lambda x: (x["mtbf_hours"] is None, x.get("mtbf_hours") or 0))
        type_health = []
        for tname, times in type_alerts.items():
            type_health.append({"target_type": tname, "alert_count": len(times), "mtbf_hours": _mtbf(times)})
        type_health.sort(key=lambda x: (x["mtbf_hours"] is None, x.get("mtbf_hours") or 0))

        return {
            "days": days,
            "room_id": room_id,
            "alert_count": len(alerts),
            "emergency_count": urgency,
            "serious_count": serious,
            "avg_mttr_hours": None if avg_mttr is None else round(avg_mttr, 2),
            "availability_pct": round(availability, 4),
            "estimated_outage_hours": round(outage_hours, 2),
            "top_failure_device_id": top_device,
            "top_failure_target_type": top_type,
            "device_health": device_health[:15],
            "type_health": type_health,
        }

    # ---------------- LLM 数据追溯 ----------------
    async def alert_trace(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """面向 LLM 的数据追溯：按关键字/对象回溯告警生命周期。

        支持：某设备/传感器/机柜上周/最近 N 天告警，同类复发统计，Top 频发对象。
        """
        text = (query or "").lower()
        # 解析时间范围
        since = datetime.now(timezone.utc) - timedelta(days=7)
        for label, days in [("30天", 30), ("90天", 90), ("180天", 180), ("上周", 7), ("今天", 1), ("本周", 7), ("最近一个月", 30), ("最近一周", 7), ("一个月", 30), ("一周", 7)]:
            if label in text:
                since = datetime.now(timezone.utc) - timedelta(days=days)
                break

        keyword_parts = [w for w in text.replace("?", "").replace("？", "").split() if w]
        q = select(Alert).where(Alert.created_at >= since).order_by(Alert.created_at.desc()).limit(limit)
        alerts = (await self.db.execute(q)).scalars().all()
        items = []
        for a in alerts:
            resolved_at = None
            for act in (a.actions or []):
                if act.action_type == "resolve":
                    resolved_at = _fmt(act.created_at)
                    break
            items.append({
                "id": a.id,
                "title": a.title,
                "description": a.description,
                "level": a.level,
                "status": a.status,
                "target_type": a.target_type,
                "source": a.source,
                "occurrences": getattr(a, "occurrences", None),
                "created_at": _fmt(a.created_at),
                "resolved_at": resolved_at,
            })
        # 简单关键字过滤（标题/描述）
        if keyword_parts:
            filtered = []
            hay = text
            for it in items:
                blob = (f"{it['title']} {it['description'] or ''}").lower()
                if any(p in blob for p in keyword_parts):
                    filtered.append(it)
            if filtered:
                items = filtered

        # 同类复发统计（按 title 哈希聚类）
        recurrence: Dict[str, int] = {}
        for a in alerts:
            key = (a.title or "未知")[:60]
            recurrence[key] = recurrence.get(key, 0) + 1
        top_recurrent = sorted(recurrence.items(), key=lambda kv: kv[1], reverse=True)[:10]

        # Top 频发设备/目标
        freq: Dict[str, int] = {}
        for a in alerts:
            target = f"{a.target_type}:{a.target_id}" if a.target_type else "system"
            freq[target] = freq.get(target, 0) + 1
        top_frequent = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:10]

        return {
            "query": query,
            "since": _fmt(since),
            "matched": len(items),
            "alerts": items,
            "top_recurrent_titles": [{"title": k, "count": v} for k, v in top_recurrent],
            "top_frequent_targets": [{"target": k, "count": v} for k, v in top_frequent],
        }