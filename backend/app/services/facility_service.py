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
    # 3D 网格布局参数（与前端 Rack3DScene 保持一致）
    GRID_COL_SPACING_M = 1.3
    GRID_ROW_SPACING_M = 1.7

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _occupied_by_room(self, room_id: int, exclude_id: int = None) -> tuple[set, set]:
        """返回机房内其它机柜占用的网格 (row,col) 与世界坐标 (x,z) 集合。

        exclude_id 用于更新场景，排除机柜自身。
        """
        stmt = select(Rack.id, Rack.row_pos, Rack.col_pos, Rack.pos_x_m, Rack.pos_z_m).where(Rack.room_id == room_id)
        if exclude_id is not None:
            stmt = stmt.where(Rack.id != exclude_id)
        rows = (await self.db.execute(stmt)).all()
        grid: set = set()
        xy: set = set()
        for _rid, row_pos, col_pos, x, z in rows:
            if row_pos is not None and col_pos is not None:
                grid.add((int(row_pos), int(col_pos)))
            if x is not None and z is not None:
                xy.add((round(float(x), 2), round(float(z), 2)))
        return grid, xy

    async def _find_free_slot(self, room_id: int, exclude_id: int = None) -> tuple[int, int]:
        """在机房内寻找第一个不冲突的网格 (row, col)，避免机柜重叠。"""
        grid, _ = await self._occupied_by_room(room_id, exclude_id=exclude_id)
        row = 1
        while True:
            col = 1
            while col <= 1000:
                if (row, col) not in grid:
                    return row, col
                col += 1
            row += 1


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
        data = req.model_dump()
        row_pos, col_pos = data.get("row_pos"), data.get("col_pos")
        pos_x, pos_z = data.get("pos_x_m"), data.get("pos_z_m")
        has_grid = row_pos is not None and col_pos is not None
        has_pos = pos_x is not None or pos_z is not None

        if not has_grid:
            # 未提供行列 => 自动补一个不冲突的网格坐标
            data["row_pos"], data["col_pos"] = await self._find_free_slot(req.room_id)
        else:
            # 已提供行列但与该机房其它机柜冲突 => 自动移到空闲格，避免重叠
            grid, _ = await self._occupied_by_room(req.room_id)
            if (int(row_pos), int(col_pos)) in grid:
                data["row_pos"], data["col_pos"] = await self._find_free_slot(req.room_id)

        # 缺世界坐标 => 由行列推导补齐，保证 3D 布局字段自洽
        if data.get("row_pos") is not None and data.get("col_pos") is not None and not has_pos:
            data["pos_x_m"] = float(data["col_pos"] - 1) * self.GRID_COL_SPACING_M
            data["pos_z_m"] = float(data["row_pos"] - 1) * self.GRID_ROW_SPACING_M

        rack = Rack(**data)
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
        if "row_pos" in data or "col_pos" in data:
            final_row = data.get("row_pos", rack.row_pos)
            final_col = data.get("col_pos", rack.col_pos)
            if final_row is not None and final_col is not None:
                # 若更新后的位置与同机房其它机柜冲突，自动移到空闲格
                grid, _ = await self._occupied_by_room(rack.room_id, exclude_id=rack.id)
                if (int(final_row), int(final_col)) in grid:
                    data["row_pos"], data["col_pos"] = await self._find_free_slot(rack.room_id, exclude_id=rack.id)
                    final_row, final_col = data["row_pos"], data["col_pos"]
                # 行列已定且世界坐标缺失且本次未显式设置 => 推导补齐
                if (data.get("pos_x_m") is None and data.get("pos_z_m") is None
                        and rack.pos_x_m is None and rack.pos_z_m is None):
                    data["pos_x_m"] = float(final_col - 1) * self.GRID_COL_SPACING_M
                    data["pos_z_m"] = float(final_row - 1) * self.GRID_ROW_SPACING_M
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
async def recompute_rack_available(db, rack_id):
    """Recompute available_units for a rack from its devices (write-path consistency).

    available_units is a derived counter; keep it in sync after device mount/umount.
    """
    if rack_id is None:
        return
    from app.models.facility import Rack
    total = (await db.execute(select(Rack.total_units).where(Rack.id == rack_id))).scalar()
    if total is None:
        return
    from app.models.device import Device
    used = 0
    rows = (await db.execute(
        select(Device).where(Device.rack_id == rack_id)
    )).scalars().all()
    for d in rows:
        if d.start_u is not None and d.end_u is not None:
            if d.end_u < d.start_u:
                continue
            used += (d.end_u - d.start_u + 1)
    new_avail = max(0, total - used)
    rack = (await db.execute(select(Rack).where(Rack.id == rack_id))).scalar_one()
    rack.available_units = new_avail

