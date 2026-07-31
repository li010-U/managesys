"""机房管理服务"""
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.facility import DataCenter, Room, Rack
from app.schemas.facility import (
    DataCenterCreate, DataCenterUpdate,
    RoomCreate, RoomUpdate,
    RackCreate, RackUpdate,
)


class DataCenterService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_list(self, page: int = 1, page_size: int = 10, keyword: str = None) -> tuple[list[DataCenter], int]:
        query = select(DataCenter)
        count_query = select(func.count(DataCenter.id))
        if keyword:
            f = DataCenter.name.ilike(f"%{keyword}%") | DataCenter.code.ilike(f"%{keyword}%")
            query = query.where(f)
            count_query = count_query.where(f)
        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(DataCenter.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_by_id(self, dc_id: int) -> DataCenter | None:
        result = await self.db.execute(select(DataCenter).where(DataCenter.id == dc_id))
        return result.scalar_one_or_none()

    async def create(self, req: DataCenterCreate, operator_username: str = None, operator_ip: str = None) -> DataCenter:
        dc = DataCenter(**req.model_dump())
        self.db.add(dc)
        await self.db.flush()
        await self.db.refresh(dc)

        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="create",
            target_type="data_center",
            target_id=str(dc.id),
            detail=f"创建数据中心: {dc.name} ({dc.code})",
            ip_address=operator_ip,
        )

        return dc

    async def update(self, dc_id: int, req: DataCenterUpdate, operator_username: str = None, operator_ip: str = None) -> DataCenter | None:
        dc = await self.get_by_id(dc_id)
        if not dc:
            return None
        for k, v in req.model_dump(exclude_unset=True).items():
            setattr(dc, k, v)
        await self.db.flush()
        await self.db.refresh(dc)

        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="update",
            target_type="data_center",
            target_id=str(dc.id),
            detail=f"更新数据中心: {dc.name}",
            ip_address=operator_ip,
        )

        return dc

    async def delete(self, dc_id: int, operator_username: str = None, operator_ip: str = None) -> bool:
        dc = await self.get_by_id(dc_id)
        if not dc:
            return False

        dc_name = dc.name
        await self.db.delete(dc)
        await self.db.flush()

        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="delete",
            target_type="data_center",
            target_id=str(dc_id),
            detail=f"删除数据中心: {dc_name}",
            ip_address=operator_ip,
        )

        return True


class RoomService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_list(self, page: int = 1, page_size: int = 10, keyword: str = None,
                       data_center_id: int = None) -> tuple[list[Room], int]:
        query = select(Room)
        count_query = select(func.count(Room.id))
        if keyword:
            f = Room.name.ilike(f"%{keyword}%") | Room.code.ilike(f"%{keyword}%")
            query = query.where(f)
            count_query = count_query.where(f)
        if data_center_id:
            query = query.where(Room.data_center_id == data_center_id)
            count_query = count_query.where(Room.data_center_id == data_center_id)
        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(Room.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_by_id(self, room_id: int) -> Room | None:
        result = await self.db.execute(select(Room).where(Room.id == room_id))
        return result.scalar_one_or_none()

    async def create(self, req: RoomCreate, operator_username: str = None, operator_ip: str = None) -> Room:
        room = Room(**req.model_dump())
        self.db.add(room)
        await self.db.flush()
        await self.db.refresh(room)

        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="create",
            target_type="room",
            target_id=str(room.id),
            detail=f"创建机房: {room.name} ({room.code})",
            ip_address=operator_ip,
        )

        return room

    async def update(self, room_id: int, req: RoomUpdate, operator_username: str = None, operator_ip: str = None) -> Room | None:
        room = await self.get_by_id(room_id)
        if not room:
            return None
        for k, v in req.model_dump(exclude_unset=True).items():
            setattr(room, k, v)
        await self.db.flush()
        await self.db.refresh(room)

        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="update",
            target_type="room",
            target_id=str(room.id),
            detail=f"更新机房: {room.name}",
            ip_address=operator_ip,
        )

        return room

    async def delete(self, room_id: int, operator_username: str = None, operator_ip: str = None) -> bool:
        room = await self.get_by_id(room_id)
        if not room:
            return False

        room_name = room.name
        await self.db.delete(room)
        await self.db.flush()

        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="delete",
            target_type="room",
            target_id=str(room_id),
            detail=f"删除机房: {room_name}",
            ip_address=operator_ip,
        )

        return True


class RackService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_list(self, page: int = 1, page_size: int = 10, keyword: str = None,
                       room_id: int = None) -> tuple[list[Rack], int]:
        query = select(Rack)
        count_query = select(func.count(Rack.id))
        if keyword:
            f = Rack.name.ilike(f"%{keyword}%") | Rack.code.ilike(f"%{keyword}%")
            query = query.where(f)
            count_query = count_query.where(f)
        if room_id:
            query = query.where(Rack.room_id == room_id)
            count_query = count_query.where(Rack.room_id == room_id)
        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(Rack.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_by_id(self, rack_id: int) -> Rack | None:
        result = await self.db.execute(select(Rack).where(Rack.id == rack_id))
        return result.scalar_one_or_none()

    async def create(self, req: RackCreate, operator_username: str = None, operator_ip: str = None) -> Rack:
        rack = Rack(**req.model_dump())
        rack.available_units = rack.total_units
        self.db.add(rack)
        await self.db.flush()
        await self.db.refresh(rack)

        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="create",
            target_type="rack",
            target_id=str(rack.id),
            detail=f"创建机柜: {rack.name} ({rack.code})",
            ip_address=operator_ip,
        )

        return rack

    async def update(self, rack_id: int, req: RackUpdate, operator_username: str = None, operator_ip: str = None) -> Rack | None:
        rack = await self.get_by_id(rack_id)
        if not rack:
            return None
        data = req.model_dump(exclude_unset=True)
        if "total_units" in data and data["total_units"] != rack.total_units:
            used = rack.total_units - rack.available_units
            data["available_units"] = max(0, data["total_units"] - used)
        for k, v in data.items():
            setattr(rack, k, v)
        await self.db.flush()
        await self.db.refresh(rack)

        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="update",
            target_type="rack",
            target_id=str(rack.id),
            detail=f"更新机柜: {rack.name}",
            ip_address=operator_ip,
        )

        return rack

    async def delete(self, rack_id: int, operator_username: str = None, operator_ip: str = None) -> bool:
        rack = await self.get_by_id(rack_id)
        if not rack:
            return False

        rack_name = rack.name
        await self.db.delete(rack)
        await self.db.flush()

        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="delete",
            target_type="rack",
            target_id=str(rack_id),
            detail=f"删除机柜: {rack_name}",
            ip_address=operator_ip,
        )

        return True
