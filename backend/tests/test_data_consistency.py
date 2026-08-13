# -*- coding: utf-8 -*-
"""数据一致性约束回归测试：外键约束开启下的引用整体性。

对应批判省第 9 点“数据一致性没有单一事实源 / 无外键约束底网”。
这里验证 SQLite 开启 PRAGMA foreign_keys=ON 时，模型里的
气联/级联约束确实生效，删除父记录不会留下孤儿条目。
"""
import pytest
from sqlalchemy import select, text
from app.models.facility import DataCenter, Room, Rack
from app.models.device import Device, DeviceLifecycle
from app.models.device_type import DeviceType
from app.models.sensor import Sensor, SensorData
from app.models.ip_address import IpAddress, IpSubnet


async def _seed_base(db):
    dc = DataCenter(name="DC", code="DC1")
    db.add(dc); await db.flush()
    room = Room(data_center_id=dc.id, name="R", code="RM-A", floor="1", area=50)
    db.add(room); await db.flush()
    rack = Rack(room_id=room.id, name="R01", code="RM-A-01", total_units=42, available_units=40)
    db.add(rack); await db.flush()
    t = DeviceType(name="server", code="SRV", category="server")
    db.add(t); await db.flush()
    return dc, room, rack, t


async def _count(db, table):
    r = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
    return r.scalar_one()


@pytest.mark.asyncio
async def test_delete_device_cascades_and_setnull_no_orphans(db_session):
    dc, room, rack, t = await _seed_base(db_session)
    dev = Device(name="d1", asset_number="A1", device_type_id=t.id, rack_id=rack.id,
                 status="running", management_ip="10.0.0.1", start_u=1, end_u=2)
    db_session.add(dev); await db_session.flush()
    # lifecycle 记录
    db_session.add(DeviceLifecycle(device_id=dev.id, action="create", from_status="in_stock", to_status="running"))
    # IP 台账占用
    sub = IpSubnet(name="sub", network="10.0.0.0", prefix=24)
    db_session.add(sub); await db_session.flush()
    db_session.add(IpAddress(subnet_id=sub.id, address="10.0.0.1", status="allocated", device_id=dev.id, used_as="management"))
    await db_session.flush()

    assert await _count(db_session, "device_lifecycles") == 1
    assert await _count(db_session, "ip_addresses") == 1

    await db_session.delete(dev)
    await db_session.flush()

    # device_lifecycles 级联删除
    assert await _count(db_session, "device_lifecycles") == 0
    # ip_addresses.device_id SET NULL（不是删除 IP）
    rows = (await db_session.execute(select(IpAddress))).scalars().all()
    assert len(rows) == 1
    assert rows[0].device_id is None
    # 不存在孤儿 device_id
    orphan = (await db_session.execute(
        text("SELECT COUNT(*) FROM ip_addresses WHERE device_id IS NOT NULL AND device_id NOT IN (SELECT id FROM devices)"))).scalar_one()
    assert orphan == 0


@pytest.mark.asyncio
async def test_delete_room_cascades_racks_and_sensors(db_session):
    dc, room, rack, t = await _seed_base(db_session)
    sens = Sensor(room_id=room.id, name="s1", code="S1", sensor_type="temperature")
    db_session.add(sens); await db_session.flush()
    db_session.add(SensorData(sensor_id=sens.id, value=25.0))
    await db_session.flush()

    assert await _count(db_session, "racks") == 1
    assert await _count(db_session, "sensors") == 1
    assert await _count(db_session, "sensor_data") == 1

    await db_session.delete(room)
    await db_session.flush()

    assert await _count(db_session, "racks") == 0
    assert await _count(db_session, "sensors") == 0
    assert await _count(db_session, "sensor_data") == 0


@pytest.mark.asyncio
async def test_delete_subnet_cascades_addresses(db_session):
    sub = IpSubnet(name="sub", network="10.0.0.0", prefix=24)
    db_session.add(sub); await db_session.flush()
    db_session.add(IpAddress(subnet_id=sub.id, address="10.0.0.5", status="reserved"))
    db_session.add(IpAddress(subnet_id=sub.id, address="10.0.0.6", status="free"))
    await db_session.flush()
    assert await _count(db_session, "ip_addresses") == 2

    await db_session.delete(sub)
    await db_session.flush()
    assert await _count(db_session, "ip_addresses") == 0
