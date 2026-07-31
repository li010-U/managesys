"""传感器管理服务"""
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensor import Sensor, SensorData
from app.schemas.sensor import SensorCreate, SensorUpdate


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

    async def get_recent_data(self, sensor_id: int, limit: int = 20):
        result = await self.db.execute(
            select(SensorData).where(SensorData.sensor_id == sensor_id)
            .order_by(SensorData.recorded_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def record_data(self, sensor_id: int, value: float):
        sd = SensorData(sensor_id=sensor_id, value=value)
        self.db.add(sd)
        sensor = await self.get_by_id(sensor_id)
        if sensor:
            sensor.current_value = {"value": value, "unit": self._get_unit(sensor.sensor_type)}
            sensor.last_update_time = datetime.now(timezone.utc)
            sensor.status = "online"
        await self.db.flush()
        await self.db.refresh(sd)
        return sd

    def _get_unit(self, sensor_type: str) -> str:
        return {"temperature": "°C", "humidity": "%RH", "smoke": "", "water": "", "door_magnetic": ""}.get(sensor_type, "")
