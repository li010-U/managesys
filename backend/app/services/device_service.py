"""设备管理服务"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device_type import DeviceType
from app.models.device import Device, DeviceLifecycle
from app.schemas.device import DeviceTypeCreate, DeviceTypeUpdate, DeviceCreate, DeviceUpdate, ThresholdConfigUpdate


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
                       device_type_id: int = None, rack_id: int = None, status: str = None) -> tuple[list[Device], int]:
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
        result = await self.db.execute(
            query.order_by(Device.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
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
        return device

    async def update(self, device_id: int, req: DeviceUpdate, operator_username: str = None, operator_ip: str = None) -> Device | None:
        device = await self.get_by_id(device_id)
        if not device:
            return None
        old_status = device.status
        data = req.model_dump(exclude_unset=True)
        for k, v in data.items():
            setattr(device, k, v)
        new_status = data.get("status", old_status)
        if old_status != new_status:
            self._add_lifecycle(device_id, "change", old_status, new_status)
        await self.db.flush()
        await self.db.refresh(device)

        # 审计日志
        from app.services.audit_service import AuditService
        detail = f"更新设备: {device.name}"
        if old_status != new_status:
            detail += f", 状态变更: {old_status} -> {new_status}"
        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="update",
            target_type="device",
            target_id=str(device.id),
            detail=detail,
            ip_address=operator_ip,
        )

        return device

    async def delete(self, device_id: int, operator_username: str = None, operator_ip: str = None) -> bool:
        device = await self.get_by_id(device_id)
        if not device:
            return False
        
        device_name = device.name
        await self.db.delete(device)
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
        old_status = device.status
        device.status = new_status
        self._add_lifecycle(device_id, "change", old_status, new_status, operator, remark)
        await self.db.flush()
        await self.db.refresh(device)

        # 审计日志
        from app.services.audit_service import AuditService
        AuditService.log(
            self.db,
            username=operator_username or operator or "system",
            action="update",
            target_type="device",
            target_id=str(device.id),
            detail=f"变更设备 {device.name} 状态: {old_status} -> {new_status}",
            ip_address=operator_ip,
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
