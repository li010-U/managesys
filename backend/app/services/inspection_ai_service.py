# -*- coding: utf-8 -*-
"""AI 辅助巡检：根据机房近期告警/环境历史自动生成重点检查清单。

规则优先保证离线可用；若配置了 LLM，则调用 LLM 把数据线索润色为可执行的
检查事项清单（可回填到巡检模板/任务项）。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.facility import Room
from app.models.sensor import Sensor, SensorData


class InspectionAIService:
    def __init__(self, db: AsyncSession, with_llm: bool = True):
        self.db = db
        self.with_llm = with_llm

    async def generate_checklist(self, room_id: int, days: int = 7) -> Dict[str, Any]:
        """生成机房重点巡检清单：数据线索 + 规则建议 + (可选)LLM 润色。"""
        room = (await self.db.get(Room, room_id))
        if room is None:
            return {"found": False}
        since = datetime.now(timezone.utc) - timedelta(days=days)

        alerts = (await self.db.execute(
            select(Alert).where(Alert.created_at >= since).order_by(Alert.created_at.desc()).limit(100)
        )).scalars().all()
        sensors = (await self.db.execute(
            select(Sensor).where(Sensor.room_id == room_id)
        )).scalars().all()

        clues: List[Dict[str, Any]] = []
        priorities = {"emergency": "高", "serious": "中", "general": "低"}

        from app.models.device import Device
        for a in alerts:
            in_room = False
            if a.target_type == "sensor" and str(a.target_id).lstrip("-").isdigit():
                s = (await self.db.execute(select(Sensor).where(Sensor.id == int(a.target_id)))).scalar_one_or_none()
                in_room = bool(s and s.room_id == room_id)
            elif a.target_type == "system":
                in_room = True
            elif a.device_id:
                dev = (await self.db.get(Device, a.device_id))
                in_room = bool(dev and dev.rack and dev.rack.room_id == room_id)
            if in_room and a.status in ("new", "acknowledged"):
                clues.append({
                    "type": "alert",
                    "priority": priorities.get(a.level, "低"),
                    "title": a.title,
                    "occurrences": getattr(a, "occurrences", 1),
                    "source": "告警",
                })

        # 环境趋势提示：传感器最近值相对基线
        for s in sensors:
            if s.sensor_type not in ("temperature", "humidity"):
                continue
            rows = (await self.db.execute(
                select(SensorData.value, SensorData.recorded_at).where(
                    SensorData.sensor_id == s.id, SensorData.recorded_at >= since
                ).order_by(SensorData.recorded_at.desc()).limit(30)
            )).all()
            recent = [r[0] for r in rows]
            if recent:
                avg = sum(recent) / len(recent)
                if s.threshold_max and avg and avg > s.threshold_max * 0.9:
                    clues.append({
                        "type": "trend",
                        "priority": "中",
                        "title": f"{s.name} 近期均值 {avg:.1f} 接近上限 {s.threshold_max}，建议重点核验",
                        "occurrences": len(recent),
                        "source": "环境趋势",
                    })

        if not clues:
            clues.append({"type": "none", "priority": "低", "title": "该机房近期无明显异常，常规巡检即可", "occurrences": 0, "source": "智能分析"})

        # 规则 checklist
        checklist: List[Dict[str, Any]] = []
        seen = set()
        for c in clues:
            if c["type"] == "none":
                continue
            item = f"{c['priority']} | {c['title']}"
            if item in seen:
                continue
            seen.add(item)
            checklist.append(c)

        summary = {
            "room_id": room_id,
            "room_name": room.name,
            "room_code": room.code,
            "days": days,
            "clue_count": len(clues),
            "checklist": checklist,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
        if self.with_llm:
            summary["llm_note"] = await self._llm_refine(summary)
        return {"found": True, **summary}

    async def _llm_refine(self, data: Dict[str, Any]) -> Optional[str]:
        try:
            from app.services.llm_service import LLMService, LLMNotConfiguredError
            svc = LLMService()
            clue_lines = "\n".join(f"- [{c.get('priority')}] {c.get('title')}" for c in data["checklist"])
            prompt = (
                "你是数据中心运维专家。根据以下机房数据线索生成一条简洁的重点巡检建议"
                f"（不超过3句话，中文）。机房：{data.get('room_name')}。\n线索：\n{clue_lines or '无'}"
            )
            return (await svc.chat([{"role": "user", "content": prompt}], max_tokens=200)).strip()
        except Exception:
            return None