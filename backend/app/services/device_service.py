"""设备管理服务"""
from sqlalchemy import select, func
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device_type import DeviceType
from app.models.device import Device, DeviceLifecycle
from app.schemas.device import DeviceTypeCreate, DeviceTypeUpdate, DeviceCreate, DeviceUpdate, ThresholdConfigUpdate
from app.services.ip_registry_service import sync_device_ip_ledger, release_device_ip_ledger

# 排序字段白名单（防任意列排序注入）
DEVICE_SORT_WHITELIST = {
    "id": Device.id, "name": Device.name, "asset_number": Device.asset_number,
    "status": Device.status, "brand": Device.brand, "model": Device.model,
    "management_ip": Device.management_ip, "power_rating": Device.power_rating,
    "created_at": Device.created_at, "updated_at": Device.updated_at,
}

# 设备状态白名单：仅允许以下取值，避免任意字符串写入破坏状态机与统计语义
ALLOWED_DEVICE_STATUSES = {
    "online", "mounted", "offline", "in_stock", "maintenance", "scrapped",
}



class DeviceTypeService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_list(self, page: int = 1, page_size: int = 10, keyword: str = None,
                       category: str = None) -> tuple[list[DeviceType], int]:
        query = select(DeviceType)
        count_query = select(func.count(DeviceType.id))
        if keyword:
            f = DeviceType.name.ilike(f"%{keyword}%")
            query = query.where(f)
            count_query = count_query.where(f)
        if category:
            query = query.where(DeviceType.category == category)
            count_query = count_query.where(DeviceType.category == category)
        total = (await self.db.execute(count_query)).scalar() or 0
        result = await self.db.execute(
            query.order_by(DeviceType.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_all(self) -> list[DeviceType]:
        result = await self.db.execute(select(DeviceType).order_by(DeviceType.name))
        return list(result.scalars().all())

    async def get_by_id(self, dt_id: int) -> DeviceType | None:
        result = await self.db.execute(select(DeviceType).where(DeviceType.id == dt_id))
        return result.scalar_one_or_none()

    async def create(self, req: DeviceTypeCreate, operator_username: str = None, operator_ip: str = None) -> DeviceType:
        dt = DeviceType(**req.model_dump())
        self.db.add(dt)
        await self.db.flush()
        await self.db.refresh(dt)

        # 审计日志
        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="create",
            target_type="device_type",
            target_id=str(dt.id),
            detail=f"创建设备类型: {dt.name}",
            ip_address=operator_ip,
        )

        return dt

    async def update(self, dt_id: int, req: DeviceTypeUpdate, operator_username: str = None, operator_ip: str = None) -> DeviceType | None:
        dt = await self.get_by_id(dt_id)
        if not dt:
            return None
        for k, v in req.model_dump(exclude_unset=True).items():
            setattr(dt, k, v)
        await self.db.flush()
        await self.db.refresh(dt)

        # 审计日志
        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="update",
            target_type="device_type",
            target_id=str(dt.id),
            detail=f"更新设备类型: {dt.name}",
            ip_address=operator_ip,
        )

        return dt

    async def update_thresholds(self, dt_id: int, req: ThresholdConfigUpdate, operator_username: str = None, operator_ip: str = None) -> DeviceType | None:
        """更新设备类型阈值配置"""
        dt = await self.get_by_id(dt_id)
        if not dt:
            return None

        dt.thresholds = [t.model_dump() for t in req.thresholds]
        await self.db.flush()
        await self.db.refresh(dt)

        # 审计日志
        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="update",
            target_type="device_type",
            target_id=str(dt.id),
            detail=f"更新设备类型 {dt.name} 阈值配置",
            ip_address=operator_ip,
        )

        return dt

    async def delete(self, dt_id: int, operator_username: str = None, operator_ip: str = None) -> bool:
        dt = await self.get_by_id(dt_id)
        if not dt:
            return False
        
        dt_name = dt.name
        dev_cnt = (await self.db.execute(
            select(func.count()).select_from(Device).where(Device.device_type_id == dt_id)
        )).scalar() or 0
        if dev_cnt:
            raise HTTPException(status_code=409, detail=f"该设备类型下仍有 {dev_cnt} 台设备，请先移除设备后再删除")
        await self.db.delete(dt)
        await self.db.flush()

        # 审计日志
        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="delete",
            target_type="device_type",
            target_id=str(dt_id),
            detail=f"删除设备类型: {dt_name}",
            ip_address=operator_ip,
        )

        return True


class DeviceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_list(self, page: int = 1, page_size: int = 10, keyword: str = None,
                       device_type_id: int = None, rack_id: int = None, status: str = None,
                       sort_by: str = None, order: str = "desc") -> tuple[list[Device], int]:
        query = select(Device)
        count_query = select(func.count(Device.id))
        if keyword:
            f = Device.name.ilike(f"%{keyword}%") | Device.asset_number.ilike(f"%{keyword}%")
            query = query.where(f)
            count_query = count_query.where(f)
        if device_type_id:
            query = query.where(Device.device_type_id == device_type_id)
            count_query = count_query.where(Device.device_type_id == device_type_id)
        if rack_id:
            query = query.where(Device.rack_id == rack_id)
            count_query = count_query.where(Device.rack_id == rack_id)
        if status:
            query = query.where(Device.status == status)
            count_query = count_query.where(Device.status == status)
        total = (await self.db.execute(count_query)).scalar() or 0
        sort_col = DEVICE_SORT_WHITELIST.get(sort_by)
        if sort_col is None:
            order_expr = Device.created_at.desc()
        elif order and order.lower() == "asc":
            order_expr = sort_col.asc()
        else:
            order_expr = sort_col.desc()
        result = await self.db.execute(
            query.order_by(order_expr, Device.id.desc()).offset((page - 1) * page_size).limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_by_id(self, device_id: int) -> Device | None:
        result = await self.db.execute(select(Device).where(Device.id == device_id))
        return result.scalar_one_or_none()

    async def create(self, req: DeviceCreate, operator_username: str = None, operator_ip: str = None) -> Device:
        device = Device(**req.model_dump())
        # 如果有 rack_id 且设备状态为 in_stock，自动改为 mounted
        if device.rack_id and device.status == "in_stock":
            device.status = "mounted"
        self.db.add(device)
        await self.db.flush()
        await self.db.refresh(device)
        # 记录生命周期
        self._add_lifecycle(device.id, "create", "in_stock", "in_stock" if not device.rack_id else "mounted")
        
        # 审计日志
        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="create",
            target_type="device",
            target_id=str(device.id),
            detail=f"创建设备: {device.name} (资产号: {device.asset_number})",
            ip_address=operator_ip,
        )

        await self.db.flush()
        # 同步 IP 台账（与设备同事务，保证唯一事实源）
        from app.services.ip_registry_service import sync_device_ip_ledger as _sync
        sync_result = await _sync(self.db, device, operator=operator_username)
        # IP 冲突联动：设备 IP 与台账既有占用冲突时，生成设备级冲突告警
        if sync_result and sync_result.get("conflict"):
            from app.services.alert_lifecycle_service import AlertLifecycleService
            await AlertLifecycleService(self.db).register_signal(
                "device", str(device.id), True,
                title="IP 地址冲突", level="serious",
                device_id=device.id, metric="ip_conflict", source="system",
            )
        if device.rack_id is not None:
            from app.services.facility_service import recompute_rack_available
            await recompute_rack_available(self.db, device.rack_id)
            await self.db.flush()
        return device

    async def update(self, device_id: int, req: DeviceUpdate, operator_username: str = None, operator_ip: str = None) -> Device | None:
        device = await self.get_by_id(device_id)
        if not device:
            return None
        old_status = device.status
        old_rack = device.rack_id
        old_start = device.start_u
        old_end = device.end_u
        data = req.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(device, k, v)
        new_status = data.get("status", old_status)
        if old_status != new_status:
            self._add_lifecycle(device_id, "change", old_status, new_status)
        # 上架/下架/挪位检测 -> 追加生命周期留痕（变更审计）
        new_rack = device.rack_id
        new_start = device.start_u
        new_end = device.end_u
        rack_moved = (old_rack is None and new_rack is not None) or \
                     (old_rack is not None and new_rack is None) or \
                     (old_rack != new_rack)
        upos_changed = (old_start, old_end) != (new_start, new_end)
        if rack_moved or upos_changed:
            if new_rack is not None and old_rack is None:
                self._add_lifecycle(device_id, "mount", "in_stock" if old_status in ("in_stock",) else old_status, "mounted")
            elif new_rack is None and old_rack is not None:
                self._add_lifecycle(device_id, "unmount", old_status, "in_stock")
            else:
                self._add_lifecycle(device_id, "move", old_status, new_status)
        await self.db.flush()
        await self.db.refresh(device)

        # 审计日志
        from app.services.audit_service import AuditService
        detail = f"更新设备: {device.name}"
        if old_status != new_status:
            detail += f", 状态变更: {old_status} -> {new_status}"
        if rack_moved or upos_changed:
            action = "mount" if (new_rack is not None and old_rack is None) else \
                     "unmount" if (new_rack is None and old_rack is not None) else "move"
            detail += f", 位置: 机柜 {old_rack or '-'}->{new_rack or '-'}, U位 {old_start or '-'}-{old_end or '-'} -> {new_start or '-'}-{new_end or '-'}"
            AuditService.log(
                self.db,
                username=operator_username or "system",
                action=action,
                target_type="device",
                target_id=str(device.id),
                detail=detail,
                ip_address=operator_ip,
            )
        else:
            AuditService.log(
                self.db,
                username=operator_username or "system",
                action="update",
                target_type="device",
                target_id=str(device.id),
                detail=detail,
                ip_address=operator_ip,
            )

        # 同步 IP 台账（与设备同事务）
        from app.services.ip_registry_service import sync_device_ip_ledger as _sync
        sync_result = await _sync(self.db, device, operator=operator_username)
        # IP 冲突联动：设备 IP 变更与台账既有占用冲突时，生成/刷新设备级冲突告警
        if sync_result and sync_result.get("conflict"):
            from app.services.alert_lifecycle_service import AlertLifecycleService
            await AlertLifecycleService(self.db).register_signal(
                "device", str(device.id), True,
                title="IP 地址冲突", level="serious",
                device_id=device.id, metric="ip_conflict", source="system",
            )
        if old_rack is not None or device.rack_id is not None:
            from app.services.facility_service import recompute_rack_available
            if old_rack is not None:
                await recompute_rack_available(self.db, old_rack)
            if device.rack_id is not None:
                await recompute_rack_available(self.db, device.rack_id)
            await self.db.flush()
        return device

    async def delete(self, device_id: int, operator_username: str = None, operator_ip: str = None) -> bool:
        device = await self.get_by_id(device_id)
        if not device:
            return False
        
        device_name = device.name
        # 释放该设备在 IP 台账中的条目（同事务）
        from app.services.ip_registry_service import release_device_ip_ledger as _release
        await _release(self.db, device_id, operator=operator_username)
        # 设备生命周期联动：删除前先关闭该设备未解决告警（同一事务，避免遗留挂起告警）
        from app.services.alert_lifecycle_service import AlertLifecycleService
        await AlertLifecycleService(self.db).resolve_open_for_device(
            device_id, reason="device_deleted",
            operator=operator_username or "system",
            note="设备已删除，自动关闭未解决告警",
        )
        
        _del_rack_id = device.rack_id
        await self.db.delete(device)
        await self.db.flush()
        if _del_rack_id is not None:
            from app.services.facility_service import recompute_rack_available
            await recompute_rack_available(self.db, _del_rack_id)
            await self.db.flush()

        # 审计日志
        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="delete",
            target_type="device",
            target_id=str(device_id),
            detail=f"删除设备: {device_name}",
            ip_address=operator_ip,
        )

        return True

    async def change_status(self, device_id: int, new_status: str, operator: str = None,
                            remark: str = None, operator_username: str = None, operator_ip: str = None) -> Device | None:
        device = await self.get_by_id(device_id)
        if not device:
            return None
        # 状态白名单校验：拒绝非法/任意字符串，避免破坏状态机与统计语义
        if new_status not in ALLOWED_DEVICE_STATUSES:
            raise ValueError(f"不支持的设备状态: {new_status}")
        old_status = device.status
        device.status = new_status
        # 生命周期“操作人”以服务端认证用户为准，不接受客户端传入的 operator 冒名
        device_operator = operator_username or operator or "system"
        self._add_lifecycle(device_id, "change", old_status, new_status, device_operator, remark)
        await self.db.flush()
        await self.db.refresh(device)

        # 审计日志
        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=device_operator,
            action="update",
            target_type="device",
            target_id=str(device.id),
            detail=f"变更设备 {device.name} 状态: {old_status} -> {new_status}",
            ip_address=operator_ip,
        )

        # 设备状态联动：下线/报废/库存/维护等非在役状态，自动关闭该设备未解决告警
        if new_status in {"offline", "scrapped", "in_stock", "maintenance"}:
            from app.services.alert_lifecycle_service import AlertLifecycleService
            await AlertLifecycleService(self.db).resolve_open_for_device(
                device.id, reason=f"device_{new_status}",
                operator=device_operator,
                note=f"设备状态变更为 {new_status}，自动关闭未解决告警",
            )

        return device
    async def get_lifecycles(self, device_id: int) -> list[DeviceLifecycle]:
        result = await self.db.execute(
            select(DeviceLifecycle).where(DeviceLifecycle.device_id == device_id)
            .order_by(DeviceLifecycle.created_at.desc())
        )
        return list(result.scalars().all())

    def _add_lifecycle(self, device_id: int, action: str, from_status: str, to_status: str,
                       operator: str = None, remark: str = None):
        lc = DeviceLifecycle(
            device_id=device_id, action=action,
            from_status=from_status, to_status=to_status,
            operator=operator, remark=remark,
        )
        self.db.add(lc)

    async def get_device_environment(self, device_id: int):
        """设备⇄机房⇄传感器关联：由设备所在机柜解析机房，返回该机房的传感器/环境快照。

        关联链：Device.rack_id -> Rack.room_id -> Room，Sensor.room_id == Room.id。
        设备未挂载机柜或无对应机房时返回空 sensors，不报错。
        """
        if device_id is None:
            return None
        device = await self.get_by_id(device_id)
        if device is None:
            return None

        from sqlalchemy import select as _sel
        from app.models.facility import Room
        from app.models.sensor import Sensor

        room_id = None
        room_name = None
        rack_id = device.rack_id
        rack_name = device.rack.name if device.rack else None
        if device.rack is not None:
            room_id = device.rack.room_id
        if room_id is not None:
            room = (await self.db.execute(_sel(Room).where(Room.id == room_id))).scalar_one_or_none()
            room_name = room.name if room else None

        sensors = []
        if room_id is not None:
            rows = (await self.db.execute(
                _sel(Sensor).where(Sensor.room_id == room_id).order_by(Sensor.name)
            )).scalars().all()
            for s in rows:
                sensors.append({
                    "id": s.id,
                    "name": s.name,
                    "code": s.code,
                    "sensor_type": s.sensor_type,
                    "status": s.status,
                    "current_value": s.current_value,
                    "last_update_time": s.last_update_time.isoformat() if s.last_update_time else None,
                    "threshold_min": s.threshold_min,
                    "threshold_max": s.threshold_max,
                })

        return {
            "device_id": device.id,
            "device_name": device.name,
            "rack_id": rack_id,
            "rack_name": rack_name,
            "room_id": room_id,
            "room_name": room_name,
            "sensors": sensors,
        }
