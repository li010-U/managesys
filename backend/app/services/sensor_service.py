"""传感器管理服务"""
from app.core.timeutil import now_local
from sqlalchemy import select, func
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensor import Sensor, SensorData
from app.schemas.sensor import SensorCreate, SensorUpdate


MAX_TREND_POINTS = 240  # 传感器趋势图最多返回点数（长周期降采样上限）


class _PointSample:
    """降采样聚合结果：与 SensorData 保持 .value / .recorded_at / id / sensor_id / source_mark
    访问契约的轻量对象，便于直接用 SensorDataResponse 校验。"""
    __slots__ = ("id", "sensor_id", "value", "recorded_at", "source_mark")


    def __init__(self, value, recorded_at, mid=None):
        self.value = value
        self.recorded_at = recorded_at
        # 从桶内中点记录继承原始 SensorData 的字段，保证可被 SensorDataResponse 校验
        self.id = mid.id if mid is not None else None
        self.sensor_id = mid.sensor_id if mid is not None else None
        self.source_mark = mid.source_mark if mid is not None else "normal"


def _summarize_bucket(bucket) -> "_PointSample":
    """把一个升序时间桶聚合成一个代表点：取中位样本 + 桶内均值。

    与 _downsample 原有逐桶逻辑保持一致，供批量与流式降采样共用。
    """
    mid = bucket[len(bucket) // 2]
    avg = sum(float(r.value) for r in bucket) / len(bucket)
    return _PointSample(value=avg, recorded_at=mid.recorded_at, mid=mid)


def _downsample(rows, max_points: int) -> list:
    """把升序的时间序列降采样到最多 max_points 个点（按时间等分桶取均值）。

    rows 为升序 SensorData 列表；返回降采样后的 _PointSample 列表（倒序，最新在前），
    与前端 reverse 契约保持一致。仅用于行数已整体载入内存的场景（行数受限）。
    """
    if not rows:
        return []
    n = len(rows)
    if n <= max_points:
        return [_PointSample(value=float(r.value), recorded_at=r.recorded_at, mid=r) for r in reversed(rows)]
    bucket_count = max(1, min(max_points, n))
    bucket_size = max(1, (n + bucket_count - 1) // bucket_count)
    sampled = []
    for idx in range(0, n, bucket_size):
        bucket = rows[idx:idx + bucket_size]
        sampled.append(_summarize_bucket(bucket))
    return list(reversed(sampled))



class SensorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_list(self, page: int = 1, page_size: int = 10, room_id: int = None,
                       sensor_type: str = None, keyword: str = None):
        query = select(Sensor)
        count_query = select(func.count(Sensor.id))
        if room_id:
            query = query.where(Sensor.room_id == room_id)
            count_query = count_query.where(Sensor.room_id == room_id)
        if sensor_type:
            query = query.where(Sensor.sensor_type == sensor_type)
            count_query = count_query.where(Sensor.sensor_type == sensor_type)
        if keyword:
            f = Sensor.name.ilike(f"%{keyword}%")
            query = query.where(f)
            count_query = count_query.where(f)
        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(Sensor.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_all(self, room_id: int = None):
        query = select(Sensor)
        if room_id:
            query = query.where(Sensor.room_id == room_id)
        result = await self.db.execute(query.order_by(Sensor.name))
        return list(result.scalars().all())

    async def get_by_id(self, sensor_id: int):
        result = await self.db.execute(select(Sensor).where(Sensor.id == sensor_id))
        return result.scalar_one_or_none()

    async def create(self, req: SensorCreate):
        sensor = Sensor(**req.model_dump())
        self.db.add(sensor)
        await self.db.flush()
        await self.db.refresh(sensor)
        return sensor

    async def update(self, sensor_id: int, req: SensorUpdate):
        sensor = await self.get_by_id(sensor_id)
        if not sensor:
            return None
        for k, v in req.model_dump(exclude_unset=True).items():
            setattr(sensor, k, v)
        await self.db.flush()
        await self.db.refresh(sensor)
        return sensor

    async def delete(self, sensor_id: int) -> bool:
        sensor = await self.get_by_id(sensor_id)
        if not sensor:
            return False
        await self.db.delete(sensor)
        await self.db.flush()
        return True

    async def get_recent_data(self, sensor_id: int, limit: int = 20, hours: Optional[float] = None):
        """查询传感器最近数据。

        - 默认（hours=None）：返回最近 limit 条（倒序，最新在前），兼容原行为。
        - 指定 hours：返回该时间窗口内的数据，并对海量采样点做时间分桶降采样，
          使半天/一天的长周期也能以有限点数完整展示（返回倒序，与前端 reverse 契约一致）。

        注意：hours 场景必须在「完整时间窗口」内降采样，不能先 LIMIT 最新 N 条——
        否则长周期窗口里数据点超过 MAX_TREND_POINTS 时，只取最新 N 条会把
        窗口绝大部分时间截掉，导致“近24小时”只显示最后十几分钟。
        """
        if hours is not None and hours > 0:
            from datetime import timedelta as _td
            from app.core.timeutil import now as _now_local
            cutoff_ts = _now_local() - _td(hours=hours)
            # 1) 统计窗口内总数，决定是否需要降采样
            total = (
                await self.db.execute(
                    select(func.count()).select_from(SensorData).where(
                        SensorData.sensor_id == sensor_id,
                        SensorData.recorded_at >= cutoff_ts,
                    )
                )
            ).scalar() or 0
            if total == 0:
                return []
            if total <= MAX_TREND_POINTS:
                # 窗口内本身就不多：直接全量返回（倒序）
                rows = list((
                    await self.db.execute(
                        select(SensorData)
                        .where(SensorData.sensor_id == sensor_id, SensorData.recorded_at >= cutoff_ts)
                        .order_by(SensorData.recorded_at.desc())
                    )
                ).scalars().all())
                return rows
            # 2) 窗口内点数超过上限：流式分桶降采样，整窗覆盖、内存恒定。
            #    不把窗口内全部行一次性载入内存，而是按桶大小分批流式读取，
            #    每桶就地聚合出一个代表点（均值 + 中位样本），内存上限约为
            #    一个桶的大小 + 已产出桶数（<= MAX_TREND_POINTS），与总量无关。
            bucket_size = (total + MAX_TREND_POINTS - 1) // MAX_TREND_POINTS
            _sstream = await self.db.stream_scalars(
                select(SensorData)
                .where(SensorData.sensor_id == sensor_id, SensorData.recorded_at >= cutoff_ts)
                .order_by(SensorData.recorded_at.asc())
                .execution_options(yield_per=bucket_size)
            )
            _sampled = []
            _buf = []
            async for _row in _sstream:
                _buf.append(_row)
                if len(_buf) >= bucket_size:
                    _sampled.append(_summarize_bucket(_buf))
                    _buf = []
            if _buf:
                _sampled.append(_summarize_bucket(_buf))
            return list(reversed(_sampled))

        # hours 未指定：保持原有“最近 limit 条”语义
        query = (
            select(SensorData)
            .where(SensorData.sensor_id == sensor_id)
            .order_by(SensorData.recorded_at.desc())
            .limit(max(limit, 1))
        )
        rows = list((await self.db.execute(query)).scalars().all())
        return rows

    async def record_data(self, sensor_id: int, value: float):
        # 传感器不存在时不写入（否则外键约束在 flush 报错 -> 500），返回 None 由路由转 404
        sensor = await self.get_by_id(sensor_id)
        if not sensor:
            return None
        breach = self._is_breach(sensor, value)
        sd = SensorData(sensor_id=sensor_id, value=value, source_mark="abnormal" if breach else "normal")
        sensor.current_value = {"value": value, "unit": self._get_unit(sensor.sensor_type)}
        sensor.last_update_time = now_local()
        sensor.status = "online"
        self.db.add(sd)
        await self.db.flush()
        await self.db.refresh(sd)
        # 与告警体系打通：越阈 -> 异常信号，恢复正常 -> 正常信号（触发自动恢复计时）
        await self._propagate_signal(sensor, breach)
        return sd

    async def _propagate_signal(self, sensor, breach: bool) -> None:
        """把传感器采集结果作为信号推入告警生命周期，使传感器越阈与告警中心一致。
        原先 record_data 只把越阈点标记为 abnormal、不产生告警；现统一进入告警生命周期。"""
        from app.services.alert_lifecycle_service import AlertLifecycleService
        await AlertLifecycleService(self.db).register_signal(
            "sensor", str(sensor.id), breach,
            title=sensor.name or f"sensor:{sensor.id}",
            level=sensor.alert_level or "general",
            metric=sensor.sensor_type,
            source="monitor",
        )
    def _is_breach(self, sensor, value: float) -> bool:
        """判断当前值是否越过阈值（上下限任一越界）。"""
        if sensor.threshold_min is not None and value < sensor.threshold_min:
            return True
        if sensor.threshold_max is not None and value > sensor.threshold_max:
            return True
        return False

    def _get_unit(self, sensor_type: str) -> str:
        return {"temperature": "°C", "humidity": "%RH", "smoke": "", "water": "", "door_magnetic": ""}.get(sensor_type, "")
