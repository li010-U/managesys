# -*- coding: utf-8 -*-
"""环境/气象数据摄入 与 偶发故障-环境关联统计。

- record: 摄入一条环境/气象数据（温度/湿度/天气/风速 + 位置），供关联统计。
- attach_nearest_env: 把偶发故障事件补充其发生时点最近的环境快照。
- correlation_by_hour / correlation_by_weather / correlation_by_env_bucket:
  输出偶发故障与天气/环境的关联性统计。
- build_report: 生成可独立打开的 HTML 可视化报表（内嵌 Chart.js 直方图/饼图）。
"""
from __future__ import annotations

import math
import random
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.timeutil import now_local
from app.db.retry import with_commit_retry
from app.models.env_weather import EnvWeatherRecord, TransientFailureEvent


def _bucket_temperature(t: Optional[float]) -> str:
    if t is None:
        return "未知"
    if t < 15:
        return "<15°C"
    if t < 25:
        return "15~25°C"
    if t < 32:
        return "25~32°C"
    if t < 38:
        return "32~38°C"
    return ">=38°C"


def _bucket_humidity(h: Optional[float]) -> str:
    if h is None:
        return "未知"
    if h < 40:
        return "<40%RH"
    if h < 60:
        return "40~60%RH"
    if h < 80:
        return "60~80%RH"
    return ">=80%RH"


def _bucket_windspeed(w: Optional[float]) -> str:
    if w is None:
        return "未知"
    if w < 3:
        return "微风(<3m/s)"
    if w < 6:
        return "和风(3~6m/s)"
    if w < 10:
        return "强风(6~10m/s)"
    return "大风(>=10m/s)"


class EnvWeatherService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        *,
        temperature: Optional[float] = None,
        humidity: Optional[float] = None,
        weather: Optional[str] = None,
        windspeed: Optional[float] = None,
        location_id: Optional[int] = None,
        location_name: Optional[str] = None,
        recorded_at: Optional[datetime] = None,
    ) -> EnvWeatherRecord:
        rec = EnvWeatherRecord(
            temperature=temperature,
            humidity=humidity,
            weather=weather,
            windspeed=windspeed,
            location_id=location_id,
            location_name=location_name,
            recorded_at=recorded_at or now_local(),
        )
        self.db.add(rec)
        await self.db.flush()
        await with_commit_retry(self.db.commit)
        await self.db.refresh(rec)
        return rec

    async def _nearest_env(self, at: datetime, location_id: Optional[int] = None) -> Optional[EnvWeatherRecord]:
        """返回时间点 at 前后最近的一条环境记录。"""
        before = (await self.db.execute(
            select(EnvWeatherRecord)
            .where(EnvWeatherRecord.recorded_at <= at)
            .order_by(EnvWeatherRecord.recorded_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        after = (await self.db.execute(
            select(EnvWeatherRecord)
            .where(EnvWeatherRecord.recorded_at > at)
            .order_by(EnvWeatherRecord.recorded_at.asc())
            .limit(1)
        )).scalar_one_or_none()
        if before is not None and after is not None:
            db_ = abs((at - before.recorded_at).total_seconds())
            da = abs((after.recorded_at - at).total_seconds())
            return before if db_ <= da else after
        return before or after

    async def attach_nearest_env(self, event: TransientFailureEvent) -> bool:
        """为偶发事件补全发生时点最近的环境/气象快照（幂等：已有值则跳过）。"""
        if event.env_temperature is not None or event.env_weather is not None:
            return False
        env = await self._nearest_env(event.started_at, event.location_id)
        if env is None:
            return False
        event.env_temperature = env.temperature
        event.env_humidity = env.humidity
        event.env_weather = env.weather
        event.env_windspeed = env.windspeed
        if event.location_name is None:
            event.location_name = env.location_name
        if event.location_id is None:
            event.location_id = env.location_id
        await with_commit_retry(self.db.commit)
        return True

    async def _transient_events(self, since: Optional[datetime] = None, until: Optional[datetime] = None) -> List[TransientFailureEvent]:
        q = select(TransientFailureEvent).order_by(TransientFailureEvent.started_at.asc())
        if since is not None:
            q = q.where(TransientFailureEvent.started_at >= since)
        if until is not None:
            q = q.where(TransientFailureEvent.started_at <= until)
        return list((await self.db.execute(q)).scalars().all())

    async def _ensure_env_on_events(self, events: List[TransientFailureEvent]) -> None:
        """批量补全缺失的环境快照。"""
        changed = False
        for ev in events:
            if ev.env_temperature is None and ev.env_weather is None:
                if ev.location_name is None:
                    pass
                try:
                    if await self.attach_nearest_env(ev):
                        changed = True
                except Exception:
                    pass
        return

    # ---------- 关联统计 ----------
    def _count_by(self, events: List[TransientFailureEvent], fn):
        counts: Dict[str, int] = {}
        for ev in events:
            k = fn(ev)
            counts[k] = counts.get(k, 0) + 1
        return counts

    async def correlation_by_hour(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """按小时分布统计偶发故障频次。"""
        events = await self._transient_events(since=since)
        counts: Dict[int, int] = {}
        for ev in events:
            h = ev.started_at.hour
            counts[h] = counts.get(h, 0) + 1
        total = len(events)
        # 排序并计算占比
        out = []
        for h in range(24):
            c = counts.get(h, 0)
            out.append({
                "hour": h,
                "count": c,
                "ratio": round(c / total, 4) if total else 0.0,
            })
        return out

    async def correlation_by_weather(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """按天气类型统计偶发故障。"""
        events = await self._transient_events(since=since)
        await self._ensure_env_on_events(events)
        counts: Dict[str, int] = {}
        for ev in events:
            w = ev.env_weather or "未知"
            counts[w] = counts.get(w, 0) + 1
        total = len(events)
        out = [{"weather": k, "count": v, "ratio": round(v / total, 4) if total else 0.0}
               for k, v in sorted(counts.items(), key=lambda x: -x[1])]
        return out

    async def correlation_by_env_bucket(self, since: Optional[datetime] = None) -> Dict[str, List[Dict[str, Any]]]:
        """按环境区间（温度/湿度/风速）统计偶发故障频次与占比。"""
        events = await self._transient_events(since=since)
        await self._ensure_env_on_events(events)
        total = len(events)
        def _ratio(counts: Dict[str, int]):
            return [{"bucket": k, "count": v, "ratio": round(v / total, 4) if total else 0.0}
                    for k, v in sorted(counts.items(), key=lambda x: -x[1])]
        return {
            "temperature": _ratio(self._count_by(events, lambda e: _bucket_temperature(e.env_temperature))),
            "humidity": _ratio(self._count_by(events, lambda e: _bucket_humidity(e.env_humidity))),
            "windspeed": _ratio(self._count_by(events, lambda e: _bucket_windspeed(e.env_windspeed))),
        }

    async def severity_summary(self, since: Optional[datetime] = None) -> Dict[str, Any]:
        """偶发故障总览：数量、平均/最大时长、最活跃时段。"""
        events = await self._transient_events(since=since)
        if not events:
            return {"count": 0, "avg_duration_seconds": 0, "max_duration_seconds": 0,
                    "min_duration_seconds": 0, "total_duration_seconds": 0}
        durations = [ev.duration_seconds or 0 for ev in events]
        return {
            "count": len(events),
            "avg_duration_seconds": int(statistics.fmean(durations)),
            "max_duration_seconds": max(durations),
            "min_duration_seconds": min(durations),
            "total_duration_seconds": sum(durations),
        }

    async def correlation_report(self, days: Optional[int] = None) -> Dict[str, Any]:
        """汇总关联统计，供 API/报表消费。"""
        days = days or settings.ENV_RETENTION_DAYS
        since = now_local() - timedelta(days=days)
        hour = await self.correlation_by_hour(since=since)
        weather = await self.correlation_by_weather(since=since)
        buckets = await self.correlation_by_env_bucket(since=since)
        summary = await self.severity_summary(since=since)
        return {
            "since": since.isoformat(),
            "days": days,
            "summary": summary,
            "by_hour": hour,
            "by_weather": weather,
            "by_env_bucket": buckets,
        }


    async def env_trend(self, hours: Optional[int] = 24, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """返回环境数据趋势（时间升序），供前端折线图使用。

        hours: 取最近多少小时（默认 24）；limit: 最多返回条数（默认全部，便于前端降采样）。
        """
        since = (now_local() - timedelta(hours=hours)) if hours else None
        q = select(EnvWeatherRecord).order_by(EnvWeatherRecord.recorded_at.asc())
        if since is not None:
            q = q.where(EnvWeatherRecord.recorded_at >= since)
        rows = list((await self.db.execute(q)).scalars().all())
        if limit and len(rows) > limit:
            # 均匀降采样，保留首尾
            idxs = set(round(i * (len(rows) - 1) / (limit - 1)) for i in range(limit))
            rows = [rows[i] for i in sorted(idxs)]
        out = []
        for r in rows:
            out.append({
                "recorded_at": r.recorded_at,
                "temperature": r.temperature,
                "humidity": r.humidity,
                "windspeed": r.windspeed,
            })
        return out


_SEASON_TEMP = {"1": 5, "2": 8, "3": 14, "4": 20, "5": 25, "6": 29,
                "7": 32, "8": 31, "9": 26, "10": 20, "11": 13, "12": 7}
_WEATHER_WMO = {0: "晴", 1: "晴", 2: "多云", 3: "阴", 45: "雾", 48: "雾",
                51: "雨", 53: "雨", 55: "雨", 61: "雨", 63: "雨", 65: "雨",
                71: "雪", 73: "雪", 75: "雪", 80: "雨", 81: "雨", 82: "雨",
                95: "雨", 96: "雨", 99: "雨"}
_OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


class EnvPoller:
    """环境/气象自动轮询采集（后台常驻任务用）。

    与 dev_tools/collect_env_weather.py 保持同一份取值口径：
    - source=sim  ：本地生成贴近真实天气的演示值
    - source=real ：调用 Open-Meteo 开放接口（无需 API Key）
    采集结果通过 EnvWeatherService.record 写入 env_weather_records。
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.service = EnvWeatherService(db)

    @staticmethod
    def _sim_values() -> dict:
        now = now_local()
        month = str(now.month)
        base = _SEASON_TEMP.get(month, 20)
        diurnal = 4 * math.sin((now.hour - 9) / 24 * 2 * math.pi)
        temperature = base + diurnal + random.uniform(-2, 2)
        weather = random.choices(["晴", "多云", "阴", "雨", "雪", "风"],
                                 weights=[4, 3, 2, 1.5, 0.6, 1])[0]
        humidity = random.uniform(35, 85)
        if weather in ("雨", "雪"):
            humidity = random.uniform(70, 95)
        windspeed = random.uniform(1, 9) if weather != "风" else random.uniform(8, 15)
        return {
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1),
            "weather": weather,
            "windspeed": round(windspeed, 1),
        }

    @staticmethod
    def _real_values(lat: float, lon: float) -> Optional[dict]:
        import json as _json
        import urllib.request as _url
        params = (f"?latitude={lat}&longitude={lon}"
                  f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m"
                  f"&timezone=Asia%2FShanghai")
        try:
            with _url.urlopen(_OPEN_METEO_URL + params, timeout=15) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
            cur = data.get("current", {})
            return {
                "temperature": cur.get("temperature_2m"),
                "humidity": cur.get("relative_humidity_2m"),
                "weather": _WEATHER_WMO.get(cur.get("weather_code", 1), "多云"),
                "windspeed": cur.get("wind_speed_10m"),
            }
        except Exception:
            return None

    async def poll_once(self, source: str = None, lat: float = None, lon: float = None,
                        location_name: str = None, location_id: int = None) -> Optional[dict]:
        """采集一次并写入，返回写入的数据；失败返回 None。"""
        from app.core.config import settings
        source = source or settings.ENV_POLL_SOURCE
        lat = settings.ENV_POLL_LAT if lat is None else lat
        lon = settings.ENV_POLL_LON if lon is None else lon
        location_name = location_name or settings.ENV_POLL_LOCATION_NAME
        location_id = settings.ENV_POLL_LOCATION_ID if location_id is None else location_id

        if source == "real":
            values = self._real_values(lat, lon) or self._sim_values()
        else:
            values = self._sim_values()

        await self.service.record(
            temperature=values.get("temperature"),
            humidity=values.get("humidity"),
            weather=values.get("weather"),
            windspeed=values.get("windspeed"),
            location_id=location_id or None,
            location_name=location_name,
        )
        return values

