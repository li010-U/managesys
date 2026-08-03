"""设备服务单元测试 - 验证 N+1 查询修复"""
import pytest

from app.services.device_service import DeviceService, DeviceTypeService
from app.models.device import Device, DeviceLifecycle
from app.models.device_type import DeviceType
from app.models.facility import Rack, Room, DataCenter
from app.schemas.device import DeviceCreate, DeviceTypeCreate


class TestDeviceServiceN1Fix:
    """测试设备服务 N+1 查询修复"""
    
    @pytest.mark.asyncio
    async def test_get_list_preloads_relationships(self, db_session):
        """测试 get_list 预加载关联数据"""
        # 创建测试数据
        dc = DataCenter(name="测试数据中心", code="DC001")
        db_session.add(dc)
        await db_session.flush()
        
        room = Room(
            data_center_id=dc.id,
            name="测试机房",
            code="RM001",
        )
        db_session.add(room)
        await db_session.flush()
        
        rack = Rack(
            room_id=room.id,
            name="测试机柜",
            code="RK001",
            total_units=42,
            available_units=42,
        )
        db_session.add(rack)
        await db_session.flush()
        
        device_type = DeviceType(name="服务器", code="SERVER", category="compute")
        db_session.add(device_type)
        await db_session.flush()
        
        # 创建多个设备
        for i in range(3):
            device = Device(
                device_type_id=device_type.id,
                rack_id=rack.id,
                name=f"测试设备{i}",
                asset_number=f"ASSET{i:03d}",
                status="mounted"
            )
            db_session.add(device)
        await db_session.commit()
        
        # 执行查询
        service = DeviceService(db_session)
        devices, total = await service.get_list(page=1, page_size=10)
        
        # 验证：所有关联应该已预加载，不应该触发额外查询
        assert len(devices) == 3
        assert total == 3
        
        # 验证关联数据可以直接访问（不会触发 N+1）
        for device in devices:
            assert device.device_type is not None
            assert device.device_type.name == "服务器"
            assert device.rack is not None
            assert device.rack.name == "测试机柜"
            assert device.rack.room is not None
            assert device.rack.room.name == "测试机房"
    
    @pytest.mark.asyncio
    async def test_get_by_id_preloads_relationships(self, db_session):
        """测试 get_by_id 预加载关联数据"""
        # 创建测试数据
        dc = DataCenter(name="测试数据中心", code="DC001")
        db_session.add(dc)
        await db_session.flush()
        
        room = Room(data_center_id=dc.id, name="测试机房", code="RM001")
        db_session.add(room)
        await db_session.flush()
        
        rack = Rack(
            room_id=room.id,
            name="测试机柜",
            code="RK001",
            total_units=42,
            available_units=42,
        )
        db_session.add(rack)
        await db_session.flush()
        
        device_type = DeviceType(name="服务器", code="SERVER", category="compute")
        db_session.add(device_type)
        await db_session.flush()
        
        device = Device(
            device_type_id=device_type.id,
            rack_id=rack.id,
            name="测试设备",
            asset_number="ASSET001",
            status="mounted"
        )
        db_session.add(device)
        await db_session.commit()
        device_id = device.id
        
        # 执行查询
        service = DeviceService(db_session)
        result = await service.get_by_id(device_id)
        
        # 验证关联数据已预加载
        assert result is not None
        assert result.device_type.name == "服务器"
        assert result.rack.name == "测试机柜"
        assert result.rack.room.name == "测试机房"


class TestDeviceTypeServiceN1Fix:
    """测试设备类型服务 N+1 查询修复"""
    
    @pytest.mark.asyncio
    async def test_get_list_preloads_devices(self, db_session):
        """测试设备类型列表预加载设备关联"""
        device_type = DeviceType(name="服务器", code="SERVER", category="compute")
        db_session.add(device_type)
        await db_session.flush()
        
        # 创建多个设备
        for i in range(3):
            device = Device(
                device_type_id=device_type.id,
                name=f"设备{i}",
                asset_number=f"ASSET{i:03d}",
                status="mounted"
            )
            db_session.add(device)
        await db_session.commit()
        
        # 执行查询
        service = DeviceTypeService(db_session)
        results, total = await service.get_list(page=1, page_size=10)
        
        # 验证
        assert len(results) == 1
        # devices 关联已预加载，可以通过 len() 获取数量
        assert len(results[0].devices) == 3


class TestDeviceServiceAuditLog:
    """测试设备服务审计日志"""
    
    @pytest.mark.asyncio
    async def test_create_device_logs_audit(self, db_session):
        """测试创建设备记录审计日志"""
        from sqlalchemy import select
        from app.models.audit_log import AuditLog
        
        device_type = DeviceType(name="服务器", code="SERVER", category="compute")
        db_session.add(device_type)
        await db_session.flush()
        
        service = DeviceService(db_session)
        req = DeviceCreate(
            device_type_id=device_type.id,
            name="测试设备",
            asset_number="ASSET001",
            status="in_stock"
        )
        
        await service.create(req, operator_username="admin", operator_ip="127.0.0.1")
        await db_session.commit()
        
        # 验证审计日志
        result = await db_session.execute(
            select(AuditLog).where(AuditLog.target_type == "device")
        )
        logs = result.scalars().all()
        assert len(logs) >= 1
        assert "创建设备" in logs[0].detail


class TestDeviceServiceChangeStatus:
    """测试设备状态变更"""
    
    @pytest.mark.asyncio
    async def test_change_status_adds_lifecycle(self, db_session):
        """测试状态变更记录生命周期"""
        device_type = DeviceType(name="服务器", code="SERVER", category="compute")
        db_session.add(device_type)
        await db_session.flush()
        
        device = Device(
            device_type_id=device_type.id,
            name="测试设备",
            asset_number="ASSET001",
            status="mounted"
        )
        db_session.add(device)
        await db_session.flush()
        device_id = device.id
        
        service = DeviceService(db_session)
        await service.change_status(
            device_id,
            new_status="offline",
            operator="admin",
            remark="维护",
            operator_username="admin",
            operator_ip="127.0.0.1"
        )
        await db_session.commit()
        
        # 验证生命周期记录
        lifecycles = await service.get_lifecycles(device_id)
        assert len(lifecycles) >= 1
        assert lifecycles[0].from_status == "mounted"
        assert lifecycles[0].to_status == "offline"
