"""机房管理服务单元测试 - 验证 N+1 查询修复"""
import pytest

from app.services.facility_service import DataCenterService, RoomService, RackService
from app.models.facility import DataCenter, Room, Rack
from app.models.device import Device
from app.schemas.facility import DataCenterCreate, RoomCreate, RackCreate


class TestDataCenterServiceN1Fix:
    """测试数据中心服务 N+1 查询修复"""
    
    @pytest.mark.asyncio
    async def test_get_list_preloads_rooms(self, db_session):
        """测试数据中心列表预加载机房关联"""
        dc = DataCenter(name="测试数据中心", code="DC001")
        db_session.add(dc)
        await db_session.flush()
        
        # 创建多个机房
        for i in range(3):
            room = Room(
                data_center_id=dc.id,
                name=f"机房{i}",
                code=f"RM{i:03d}",
            )
            db_session.add(room)
        await db_session.commit()
        
        # 执行查询
        service = DataCenterService(db_session)
        results, total = await service.get_list(page=1, page_size=10)
        
        # 验证：关联应已预加载
        assert len(results) == 1
        # rooms 关联已预加载
        assert len(results[0].rooms) == 3


class TestRoomServiceN1Fix:
    """测试机房服务 N+1 查询修复"""
    
    @pytest.mark.asyncio
    async def test_get_list_preloads_relationships(self, db_session):
        """测试机房列表预加载机柜和数据中心关联"""
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
        
        for i in range(3):
            rack = Rack(
                room_id=room.id,
                name=f"机柜{i}",
                code=f"RK{i:03d}",
                total_units=42,
                available_units=42,
            )
            db_session.add(rack)
        await db_session.commit()
        
        service = RoomService(db_session)
        results, total = await service.get_list(page=1, page_size=10)
        
        assert len(results) == 1
        assert len(results[0].racks) == 3
        assert results[0].racks[0].name == "机柜0"
        assert results[0].data_center.name == "测试数据中心"


class TestRackServiceN1Fix:
    """测试机柜服务 N+1 查询修复"""
    
    @pytest.mark.asyncio
    async def test_get_list_preloads_relationships(self, db_session):
        """测试机柜列表预加载设备和机房关联"""
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
        
        from app.models.device_type import DeviceType
        device_type = DeviceType(name="服务器", code="SERVER", category="compute")
        db_session.add(device_type)
        await db_session.flush()
        
        for i in range(3):
            device = Device(
                device_type_id=device_type.id,
                rack_id=rack.id,
                name=f"设备{i}",
                asset_number=f"ASSET{i:03d}",
                status="mounted"
            )
            db_session.add(device)
        await db_session.commit()
        
        service = RackService(db_session)
        results, total = await service.get_list(page=1, page_size=10)
        
        assert len(results) == 1
        assert len(results[0].devices) == 3
        assert results[0].devices[0].name == "设备0"
        assert results[0].room.name == "测试机房"


class TestFacilityServiceCRUD:
    """测试机房管理 CRUD 操作"""
    
    @pytest.mark.asyncio
    async def test_create_data_center(self, db_session):
        """测试创建数据中心"""
        service = DataCenterService(db_session)
        req = DataCenterCreate(
            name="新数据中心",
            code="DC-NEW",
            address="测试地址",
        )
        
        dc = await service.create(req, operator_username="admin", operator_ip="127.0.0.1")
        await db_session.commit()
        
        assert dc.id is not None
        assert dc.name == "新数据中心"
        assert dc.code == "DC-NEW"
    
    @pytest.mark.asyncio
    async def test_create_room(self, db_session):
        """测试创建机房"""
        dc = DataCenter(name="测试DC", code="DC001")
        db_session.add(dc)
        await db_session.flush()
        
        service = RoomService(db_session)
        req = RoomCreate(
            data_center_id=dc.id,
            name="新机房",
            code="RM-NEW",
            floor="1楼",
        )
        
        room = await service.create(req, operator_username="admin", operator_ip="127.0.0.1")
        await db_session.commit()
        
        assert room.id is not None
        assert room.name == "新机房"
    
    @pytest.mark.asyncio
    async def test_create_rack_calculates_available_units(self, db_session):
        """测试创建机柜自动计算可用U位"""
        dc = DataCenter(name="测试DC", code="DC001")
        db_session.add(dc)
        await db_session.flush()
        
        room = Room(data_center_id=dc.id, name="测试机房", code="RM001")
        db_session.add(room)
        await db_session.flush()
        
        service = RackService(db_session)
        req = RackCreate(
            room_id=room.id,
            name="新机柜",
            code="RK-NEW",
            total_units=42,
        )
        
        rack = await service.create(req, operator_username="admin", operator_ip="127.0.0.1")
        await db_session.commit()
        
        assert rack.available_units == 42
    
    @pytest.mark.asyncio
    async def test_update_rack_recalculates_available_units(self, db_session):
        """测试更新机柜时重新计算可用U位"""
        dc = DataCenter(name="测试DC", code="DC001")
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
            available_units=30,
        )
        db_session.add(rack)
        await db_session.flush()
        
        service = RackService(db_session)
        req = RackCreate(
            room_id=room.id,
            name="测试机柜",
            code="RK001",
            total_units=48,
        )
        
        updated = await service.update(rack.id, req, operator_username="admin", operator_ip="127.0.0.1")
        
        assert updated.total_units == 48
        assert updated.available_units == 36
    
    @pytest.mark.asyncio
    async def test_delete_returns_false_for_nonexistent(self, db_session):
        """测试删除不存在的资源返回 False"""
        service = DataCenterService(db_session)
        result = await service.delete(99999)
        assert result is False
