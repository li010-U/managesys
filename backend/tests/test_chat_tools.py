"""AI chat tool-calling / confirmed-execution tests."""

import pytest

from app.services import ai_tools


def _super():
    from app.models import User
    return User(username="tool_admin", hashed_password="x", is_active=True, is_super_admin=True)

def _normal(username="tool_user"):
    from app.models import User
    return User(username=username, hashed_password="x", is_active=True, is_super_admin=False)

async def _rack_chain(db, code, units):
    from app.models import DataCenter, Room, Rack
    dc = DataCenter(name="DC-" + code, code="DC-" + code)
    db.add(dc); await db.flush()
    room = Room(data_center_id=dc.id, name="Room-" + code, code="RM-" + code)
    db.add(room); await db.flush()
    rack = Rack(room_id=room.id, name=code, code=code, total_units=units, available_units=units)
    db.add(rack); await db.flush()
    return rack


def test_parse_proposal_create_work_order():
    p = ai_tools.parse_proposal("创建工单 标题: 服务器故障", "已为您创建工单")
    assert p is not None
    assert p["tool"] == "create_work_order"
    assert p["args"]["title"] == "服务器故障"
    assert p["args"]["priority"] == "normal"


def test_parse_proposal_handle_alert():
    p = ai_tools.parse_proposal("请处理告警 #12 解决", "")
    assert p is not None
    assert p["tool"] == "handle_alert"
    assert p["args"]["alert_id"] == 12
    assert p["args"]["action_type"] == "resolve"


def test_parse_proposal_assign_close_verify_mount():
    p = ai_tools.parse_proposal("分配工单 #7 给 zhangsan", "")
    assert p is not None and p["tool"] == "assign_work_order" and p["args"]["assignee_username"] == "zhangsan"
    p = ai_tools.parse_proposal("关闭工单 #3", "")
    assert p is not None and p["tool"] == "close_work_order" and p["args"]["order_id"] == 3
    p = ai_tools.parse_proposal("验收工单 #3 通过 满意度 5", "")
    assert p is not None and p["tool"] == "verify_work_order" and p["args"]["accept"] is True
    p = ai_tools.parse_proposal("挂载设备 #10 到机柜 #2", "")
    assert p is not None and p["tool"] == "mount_device" and p["args"]["rack_id"] == 2
    p = ai_tools.parse_proposal("卸载设备 #10", "")
    assert p is not None and p["tool"] == "unmount_device" and p["args"]["device_id"] == 10


def test_parse_proposal_non_actionable():
    assert ai_tools.parse_proposal("今天天气如何", "今天天气不错") is None
    assert ai_tools.parse_proposal("hello", "hi there") is None
    assert ai_tools.parse_proposal("设备数量多少", "") is None


@pytest.mark.asyncio
async def test_execute_create_work_order(db_session):
    db_session.add(_super())
    await db_session.flush()
    result = await ai_tools.execute(db_session, "create_work_order", {"title": "测试工单", "priority": "high"}, _super())
    assert result["result"] == "created"
    assert result["order_no"]
    assert result["priority"] == "high"


@pytest.mark.asyncio
async def test_execute_assign_and_verify(db_session):
    admin = _super(); assignee = _normal("zhangsan")
    db_session.add_all([admin, assignee]); await db_session.flush()
    res = await ai_tools.execute(db_session, "create_work_order", {"title": "硬件维护"}, admin)
    oid = res["order_id"]
    r2 = await ai_tools.execute(db_session, "assign_work_order", {"order_id": oid, "assignee_username": "zhangsan"}, admin)
    assert r2["result"] == "assigned" and r2["assignee"] == "zhangsan"
    r3 = await ai_tools.execute(db_session, "verify_work_order", {"order_id": oid, "satisfaction": 5, "accept": True}, admin)
    assert r3["result"] == "accepted"


@pytest.mark.asyncio
async def test_execute_close_work_order(db_session):
    admin = _super()
    db_session.add(admin); await db_session.flush()
    res = await ai_tools.execute(db_session, "create_work_order", {"title": "测试工单"}, admin)
    r = await ai_tools.execute(db_session, "close_work_order", {"order_id": res["order_id"]}, admin)
    assert r["result"] == "closed"


@pytest.mark.asyncio
async def test_execute_permission_denied(db_session):
    from sqlalchemy import select
    from app.models import User
    from app.services.ai_tools import PermissionDeniedError
    plain = _normal()
    db_session.add(plain); await db_session.flush()
    # load back eagerly so the roles relationship is populated (like get_current_user)
    plain = (await db_session.execute(select(User).where(User.id == plain.id))).scalar_one()
    try:
        await ai_tools.execute(db_session, "create_work_order", {"title": "测试工单"}, plain)
        assert False, "should raise permission denied"
    except PermissionDeniedError:
        pass


@pytest.mark.asyncio
async def test_execute_unknown_tool_raises(db_session):
    admin = _super(); db_session.add(admin); await db_session.flush()
    try:
        await ai_tools.execute(db_session, "nonexistent", {}, admin)
        assert False, "should raise"
    except ValueError:
        pass
@pytest.mark.asyncio
async def test_execute_mount_unmount_capacity(db_session):
    from sqlalchemy import select
    from app.models import Device, DeviceType, Rack
    admin = _super()
    db_session.add(admin); await db_session.flush()
    dt = DeviceType(name="server", code="srv", category="server")
    db_session.add(dt); await db_session.flush()
    rack = await _rack_chain(db_session, "R1", 42)
    # 4U device
    dev = Device(device_type_id=dt.id, rack_id=None, name="srv-01", asset_number="SN001", status="in_stock", start_u=1, end_u=4)
    db_session.add(dev); await db_session.flush()

    r = await ai_tools.execute(db_session, "mount_device", {"device_id": dev.id, "rack_id": rack.id}, admin)
    assert r["result"] == "mounted"
    assert r["u_used"] == 4
    fresh_rack = (await db_session.execute(select(Rack).where(Rack.id == rack.id))).scalar_one()
    assert fresh_rack.available_units == 38

    r2 = await ai_tools.execute(db_session, "unmount_device", {"device_id": dev.id}, admin)
    assert r2["result"] == "unmounted"
    fresh_rack2 = (await db_session.execute(select(Rack).where(Rack.id == rack.id))).scalar_one()
    assert fresh_rack2.available_units == 42


@pytest.mark.asyncio
async def test_execute_mount_capacity_exceeded(db_session):
    from sqlalchemy import select
    from app.models import Device, DeviceType, Rack
    admin = _super(); db_session.add(admin); await db_session.flush()
    dt = DeviceType(name="server", code="srv2", category="server"); db_session.add(dt); await db_session.flush()
    rack = await _rack_chain(db_session, "R2", 2)
    dev = Device(device_type_id=dt.id, rack_id=None, name="big", asset_number="SN002", status="in_stock", start_u=1, end_u=4)
    db_session.add(dev); await db_session.flush()
    try:
        await ai_tools.execute(db_session, "mount_device", {"device_id": dev.id, "rack_id": rack.id}, admin)
        assert False, "should fail capacity"
    except ValueError as e:
        assert "capacity" in str(e)