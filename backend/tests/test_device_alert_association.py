# -*- coding: utf-8 -*-
"""设备生命周期与告警联动（同事务）回归测试。

设备下架/报废/删除时，应自动关闭其未解决告警并写入处理留痕。
"""
import pytest
from sqlalchemy import select

from app.models.alert import Alert, AlertAction
from app.models.device import Device
from app.models.device_type import DeviceType
from app.services.alert_lifecycle_service import AlertLifecycleService
from app.services.device_service import DeviceService


@pytest.fixture
def lifecycle(db_session):
    return AlertLifecycleService(db_session, auto_resolve_minutes=30,
                                 transient_max_seconds=300, cooldown_minutes=5)


async def _make_device(db_session):
    dt = DeviceType(name="服务器", code="server-001", category="server")
    db_session.add(dt)
    await db_session.flush()
    device = Device(device_type_id=dt.id, name="测试设备", asset_number="ASSET-ASSOC-001")
    db_session.add(device)
    await db_session.flush()
    return device


async def _open_count(db_session, device_id):
    res = await db_session.execute(
        select(Alert).where(
            Alert.device_id == device_id,
            Alert.status.in_(["new", "acknowledged"]),
        )
    )
    return len(res.scalars().all())


@pytest.mark.asyncio
async def test_resolve_open_for_device_closes_alerts(db_session, lifecycle):
    device = await _make_device(db_session)
    await lifecycle.register_signal("device", str(device.id), True, device_id=device.id, title="高温")
    assert await _open_count(db_session, device.id) == 1

    resolved = await lifecycle.resolve_open_for_device(device.id, "device_scrapped", operator="admin", note="报废联动")
    assert len(resolved) == 1

    alert = (await db_session.execute(select(Alert).where(Alert.device_id == device.id))).scalars().one()
    assert alert.status == "resolved"
    assert alert.lifecycle_action == "device_scrapped"
    assert alert.resolved_at is not None
    assert alert.cooldown_until is not None

    actions = (await db_session.execute(select(AlertAction))).scalars().all()
    assert len(actions) == 1
    assert actions[0].action_type == "resolve"
    assert actions[0].operator == "admin"


@pytest.mark.asyncio
async def test_change_status_scrapped_auto_closes_alerts(db_session):
    device = await _make_device(db_session)
    svc = AlertLifecycleService(db_session)
    await svc.register_signal("device", str(device.id), True, device_id=device.id, title="高温")
    assert await _open_count(db_session, device.id) == 1

    ds = DeviceService(db_session)
    await ds.change_status(device.id, "scrapped", operator_username="admin")
    await db_session.flush()

    assert await _open_count(db_session, device.id) == 0
    alert = (await db_session.execute(select(Alert).where(Alert.device_id == device.id))).scalars().one()
    assert alert.status == "resolved"
    assert alert.lifecycle_action == "device_scrapped"


@pytest.mark.asyncio
async def test_change_status_online_keeps_alerts_open(db_session):
    device = await _make_device(db_session)
    svc = AlertLifecycleService(db_session)
    await svc.register_signal("device", str(device.id), True, device_id=device.id, title="高温")

    ds = DeviceService(db_session)
    await ds.change_status(device.id, "online", operator_username="admin")

    assert await _open_count(db_session, device.id) == 1


@pytest.mark.asyncio
async def test_delete_device_closes_open_alerts_before_removal(db_session):
    device = await _make_device(db_session)
    svc = AlertLifecycleService(db_session)
    await svc.register_signal("device", str(device.id), True, device_id=device.id, title="高温")

    ds = DeviceService(db_session)
    ok = await ds.delete(device.id, operator_username="admin")
    assert ok is True

    alert = (await db_session.execute(
        select(Alert).where(Alert.target_id == str(device.id))
    )).scalars().one()
    assert alert.status == "resolved"
    assert alert.lifecycle_action == "device_deleted"


@pytest.mark.asyncio
async def test_ip_conflict_creates_alert(db_session):
    from app.schemas.device import DeviceCreate, DeviceUpdate
    dt = DeviceType(name="服务器", code="server-ip", category="server")
    db_session.add(dt)
    await db_session.flush()
    ds = DeviceService(db_session)
    # A 占用 10.0.0.10
    va = await ds.create(DeviceCreate(name="A", asset_number="ASSET-IP-A",
                                      device_type_id=dt.id, management_ip="10.0.0.10"))
    # B 试图占用同一 IP -> 冲突，应生成设备级冲突告警
    vb = await ds.create(DeviceCreate(name="B", asset_number="ASSET-IP-B",
                                      device_type_id=dt.id))
    await ds.update(vb.id, DeviceUpdate(management_ip="10.0.0.10"))
    alert = (await db_session.execute(
        select(Alert).where(Alert.device_id == vb.id,
                            Alert.status.in_(["new", "acknowledged"]))
    )).scalars().one()
    assert alert.level == "serious"
    assert alert.title == "IP 地址冲突"


@pytest.mark.asyncio
async def test_device_room_sensor_environment_linkage(db_session):
    from app.models.facility import DataCenter, Room, Rack
    from app.models.sensor import Sensor
    dt = DeviceType(name="服务器", code="server-env", category="server")
    db_session.add(dt)
    await db_session.flush()
    dc = DataCenter(name="中心X", code="DC-X")
    db_session.add(dc)
    await db_session.flush()
    room = Room(data_center_id=dc.id, code="R-A", name="主机房A")
    db_session.add(room)
    await db_session.flush()
    rack = Rack(room_id=room.id, code="A-01", name="A-01")
    db_session.add(rack)
    await db_session.flush()
    device = Device(device_type_id=dt.id, name="设备甲", asset_number="ASSET-ENV-001", rack_id=rack.id, status="online")
    db_session.add(device)
    await db_session.flush()
    sensor = Sensor(room_id=room.id, name="温度1", code="T-001", sensor_type="temperature",
                    status="online", current_value={"value": 24.5})
    db_session.add(sensor)
    await db_session.flush()

    ds = DeviceService(db_session)
    data = await ds.get_device_environment(device.id)
    assert data is not None
    assert data["room_id"] == room.id
    assert data["room_name"] == "主机房A"
    assert data["rack_name"] == "A-01"
    assert data["sensors"][0]["id"] == sensor.id
    assert data["sensors"][0]["sensor_type"] == "temperature"


@pytest.mark.asyncio
async def test_device_environment_none_for_missing(db_session):
    ds = DeviceService(db_session)
    assert await ds.get_device_environment(999999) is None
