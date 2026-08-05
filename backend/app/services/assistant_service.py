"""AI 桌宠助手 - 实时统计与智能提醒服务

基于规则引擎聚合系统实时数据，生成主动提醒与建议。
无需外部大模型依赖；如需接入 LLM，可在 generate_advisor 处扩展。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.device import Device
from app.models.facility import Room, Rack
from app.models.sensor import Sensor

# 指标中文名 / 单位
SENSOR_UNITS = {
    "temperature": "℃",
    "humidity": "%RH",
    "smoke": "",
    "water": "",
    "door_magnetic": "",
}
SENSOR_NAMES = {
    "temperature": "温度",
    "humidity": "湿度",
    "smoke": "烟雾",
    "water": "水浸",
    "door_magnetic": "门磁",
}


def _fmt_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone().isoformat()


def _sensor_unit(stype: str) -> str:
    return SENSOR_UNITS.get(stype, "")


def _sensor_name(stype: str) -> str:
    return SENSOR_NAMES.get(stype, stype)


class AssistantService:
    """聚合实时数据快照并基于规则生成提醒/建议。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------------- 数据快照 ----------------
    async def build_snapshot(self) -> Dict[str, Any]:
        alert_stats = await self._alert_stats()
        sensors = await self._all_sensors()
        rack_summary, high_racks = await self._rack_summary()
        device_count = await self._device_count()
        room_count = await self._room_count()
        online_sensor = sum(1 for s in sensors if s.status == "online")
        abnormal_sensors = self._abnormal_sensors(sensors)
        latest_alerts = await self._latest_alerts(limit=5)

        return {
            "timestamp": _fmt_dt(datetime.now(timezone.utc)),
            "alert_stats": alert_stats,
            "sensor": {
                "total": len(sensors),
                "online": online_sensor,
                "offline": len(sensors) - online_sensor,
                "abnormal": len(abnormal_sensors),
                "abnormal_items": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "room_id": s.room_id,
                        "sensor_type": s.sensor_type,
                        "sensor_type_name": _sensor_name(s.sensor_type),
                        "current_value": self._value_display(s),
                        "threshold_min": s.threshold_min,
                        "threshold_max": s.threshold_max,
                    }
                    for s in abnormal_sensors[:8]
                ],
            },
            "rack": rack_summary,
            "device_count": device_count,
            "room_count": room_count,
            "latest_alerts": latest_alerts,
            "high_usage_racks": high_racks[:8],
        }

    # ---------------- 子查询 ----------------
    async def _alert_stats(self) -> Dict[str, int]:
        rows = await self.db.execute(
            select(Alert.status, func.count()).group_by(Alert.status)
        )
        stats = {"new": 0, "acknowledged": 0, "resolved": 0, "ignored": 0, "total": 0}
        for status, cnt in rows.all():
            key = status or "new"
            if key in stats:
                stats[key] = cnt
            stats["total"] += cnt
        return stats

    async def _latest_alerts(self, limit: int = 5) -> List[Dict[str, Any]]:
        rows = await self.db.execute(
            select(Alert).order_by(Alert.created_at.desc()).limit(limit)
        )
        out = []
        for a in rows.scalars().all():
            out.append(
                {
                    "id": a.id,
                    "title": a.title,
                    "level": a.level,
                    "status": a.status,
                    "target_type": a.target_type,
                    "created_at": _fmt_dt(a.created_at),
                }
            )
        return out

    async def _all_sensors(self) -> List[Sensor]:
        rows = await self.db.execute(select(Sensor))
        return list(rows.scalars().all())

    def _value_display(self, s: Sensor) -> Optional[str]:
        cv = s.current_value
        if isinstance(cv, dict) and "value" in cv:
            return f"{cv['value']}{cv.get('unit', _sensor_unit(s.sensor_type))}"
        return None

    def _abnormal_sensors(self, sensors: List[Sensor]) -> List[Sensor]:
        abnormal = []
        for s in sensors:
            cv = s.current_value
            if not isinstance(cv, dict) or "value" not in cv:
                continue
            val = cv["value"]
            tmin, tmax = s.threshold_min, s.threshold_max
            if (tmin is not None and val is not None and val < tmin) or (
                tmax is not None and val is not None and val > tmax
            ):
                abnormal.append(s)
        return abnormal

    async def _rack_summary(self) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
        rows = await self.db.execute(select(Rack))
        racks = list(rows.scalars().all())
        total = len(racks)
        used = sum((r.total_units or 0) - (r.available_units or 0) for r in racks)
        capacity = sum(r.total_units or 0 for r in racks)
        high = []
        for r in racks:
            if not r.total_units:
                continue
            usage = round((r.total_units - (r.available_units or 0)) / r.total_units * 100, 1)
            if usage >= 80:
                high.append(
                    {
                        "id": r.id,
                        "code": r.code,
                        "name": r.name,
                        "usage": usage,
                        "room_id": r.room_id,
                    }
                )
        high.sort(key=lambda x: -x["usage"])
        return {
            "total": total,
            "used_units": used,
            "capacity_units": capacity,
            "avg_usage": round(used / capacity * 100, 1) if capacity else 0.0,
        }, high

    async def _device_count(self) -> int:
        rows = await self.db.execute(select(func.count()).select_from(Device))
        return rows.scalar() or 0

    async def _room_count(self) -> int:
        rows = await self.db.execute(select(func.count()).select_from(Room))
        return rows.scalar() or 0

    # ---------------- 规则引擎：主动提醒与建议 ----------------
    def generate_reminders(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        """基于快照生成主动提醒/建议。每条含 type/level/title/content。"""
        reminders: List[Dict[str, Any]] = []

        # 1. 未处理告警
        new = snapshot.get("alert_stats", {}).get("new", 0)
        if new > 0:
            reminders.append(
                {
                    "type": "alert",
                    "level": "danger",
                    "title": f"有 {new} 条告警待处理",
                    "content": f"当前有 {new} 条未处理的告警，建议尽快查看并处理，避免影响业务运行。",
                }
            )

        # 2. 传感器异常
        abnormal = snapshot.get("sensor", {}).get("abnormal", 0)
        if abnormal > 0:
            names = "、".join(i["name"] for i in snapshot["sensor"]["abnormal_items"][:3])
            reminders.append(
                {
                    "type": "env",
                    "level": "warning",
                    "title": f"{abnormal} 个传感器数据越限",
                    "content": f"以下传感器超出阈值：{names}。请检查对应机房环境。",
                }
            )

        # 3. 传感器离线
        offline = snapshot.get("sensor", {}).get("offline", 0)
        if offline > 0:
            reminders.append(
                {
                    "type": "env",
                    "level": "info",
                    "title": f"{offline} 个传感器离线",
                    "content": f"有 {offline} 个传感器处于离线状态，可能是网络或供电问题，建议排查。",
                }
            )

        # 4. 机柜高利用率
        high_num = len(snapshot.get("high_usage_racks", []))
        if high_num > 0:
            codes = "、".join(r["code"] for r in snapshot["high_usage_racks"][:3])
            reminders.append(
                {
                    "type": "capacity",
                    "level": "warning",
                    "title": f"{high_num} 个机柜利用率超过 80%",
                    "content": f"机柜 {codes} 空间紧张，建议提前规划扩容或上架调整。",
                }
            )

        # 5. 机柜整体利用率提示
        avg_usage = snapshot.get("rack", {}).get("avg_usage", 0)
        if avg_usage < 30 and snapshot.get("rack", {}).get("total", 0) > 0:
            reminders.append(
                {
                    "type": "capacity",
                    "level": "info",
                    "title": "机柜整体利用率偏低",
                    "content": f"当前机柜平均利用率约 {avg_usage}%，可考虑集中整合以降低能耗。",
                }
            )

        return reminders

    def build_context_text(self, snapshot: Dict[str, Any]) -> str:
        """生成业务上下文简要文本，作为 LLM 的 grounding 事实来源。"""
        lines = []
        s = snapshot.get("sensor", {})
        alert = snapshot.get("alert_stats", {})
        rack = snapshot.get("rack", {})
        lines.append(f"设备数: {snapshot.get('device_count', 0)}; 机房数: {snapshot.get('room_count', 0)}")
        lines.append(
            f"传感器: 总 {s.get('total', 0)} 个, 在线 {s.get('online', 0)}, "
            f"离线 {s.get('offline', 0)}, 超阈值异常 {s.get('abnormal', 0)}"
        )
        if s.get("abnormal_items"):
            names = "、".join(i["name"] for i in s["abnormal_items"][:10])
            lines.append(f"异常传感器: {names}")
        lines.append(
            f"告警: 总 {alert.get('total', 0)}, 待处理 {alert.get('new', 0)}, "
            f"已确认 {alert.get('acknowledged', 0)}, 已解决 {alert.get('resolved', 0)}"
        )
        if snapshot.get("latest_alerts"):
            alerts = "、".join(f"{a['title']}({a['level']})" for a in snapshot["latest_alerts"][:5])
            lines.append(f"最新告警: {alerts}")
        lines.append(
            f"机柜: 总 {rack.get('total', 0)} 个, 已用 {rack.get('used_units', 0)}/"
            f"{rack.get('capacity_units', 0)} 单元, 平均利用率 {rack.get('avg_usage', 0)}%"
        )
        if snapshot.get("high_usage_racks"):
            hs = "、".join(f"{h['code']}({h['usage']}%)" for h in snapshot["high_usage_racks"][:8])
            lines.append(f"高利用率(≥80%)机柜: {hs}")
        return "\n".join(lines)


    def generate_advisor(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """生成一段综合的健康度评语与建议（规则聚合，可扩展为 LLM 生成）。"""
        alert_stats = snapshot.get("alert_stats", {})
        sensor = snapshot.get("sensor", {})
        rack = snapshot.get("rack", {})

        issues = 0
        if alert_stats.get("new", 0):
            issues += 1
        if sensor.get("abnormal", 0):
            issues += 1
        if sensor.get("offline", 0):
            issues += 1
        if len(snapshot.get("high_usage_racks", [])):
            issues += 1

        if issues == 0:
            status = "healthy"
            mood = "很好"
            summary = (
                f"系统一切正常：{snapshot.get('device_count', 0)} 台设备、"
                f"{snapshot.get('room_count', 0)} 个机房，环境与机柜均处于健康状态，继续保持！"
            )
        elif issues <= 2:
            status = "attention"
            mood = "一般"
            summary = "部分指标需要关注，建议查看告警与环境数据。"
        else:
            status = "alert"
            mood = "较差"
            summary = "系统存在多处异常，请尽快处理告警并排查环境问题。"

        return {
            "status": status,
            "mood": mood,
            "summary": summary,
            "metrics": {
                "devices": snapshot.get("device_count", 0),
                "rooms": snapshot.get("room_count", 0),
                "new_alerts": alert_stats.get("new", 0),
                "abnormal_sensors": sensor.get("abnormal", 0),
                "offline_sensors": sensor.get("offline", 0),
                "rack_avg_usage": rack.get("avg_usage", 0),
            },
        }
