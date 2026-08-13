# -*- coding: utf-8 -*-
"""3D/2D 场景数据与区域切换 合同测试。

覆盖高频回归点：
- 机房 3D 场景聚合数据 /rooms/{id}/rack3d 结构（机柜/设备U位/功率/利用率/温度）
- 区域切换（机房间数据隔离）
- 2D U 位数据源（设备 start_u/end_u）
- 机房不存在时 ValueError/404语义
"""
import pytest
from fastapi import HTTPException

from app.api.v1.facilities import room_rack3d
from app.models.facility import DataCenter, Room, Rack
from app.models.device import Device
from app.models.device_type import DeviceType


class _FakeUser:
    id = 1
    username = "admin"


async def _seed(db_session, name, code, floor, racks_spec):
    """搭种一个机房。返回 room.id。"""
    from sqlalchemy import select
    dc = (await db_session.execute(select(DataCenter).where(DataCenter.code == "DC1"))).scalar_one_or_none()
    if dc is None:
        dc = DataCenter(name="DC", code="DC1")
        db_session.add(dc)
        await db_session.flush()
    t = (await db_session.execute(select(DeviceType).where(DeviceType.code == "SRV"))).scalar_one_or_none()
    if t is None:
        t = DeviceType(name="server", code="SRV", category="server")
        db_session.add(t)
        await db_session.flush()
    room = Room(data_center_id=dc.id, name=name, code=code, floor=floor, area=120.5, status="active")
    db_session.add(room)
    await db_session.flush()
    for spec in racks_spec:
        rack = Rack(room_id=room.id, name=spec["name"], code=spec["code"],
                    row_pos=0, col_pos=0, total_units=spec.get("total_units", 42),
                    available_units=spec.get("available_units", 39),
                    rated_power=spec.get("rated_power"))
        db_session.add(rack)
        await db_session.flush()
        for dev in spec.get("devices", []):
            db_session.add(Device(name=dev["name"], asset_number=dev["asset_number"], device_type_id=t.id,
                                  rack_id=rack.id, start_u=dev["start_u"], end_u=dev["end_u"],
                                  status=dev.get("status", "mounted"),
                                  power_rating=dev.get("power_rating"),
                                  management_ip=dev.get("management_ip")))
    await db_session.flush()
    return room.id


@pytest.mark.asyncio
async def test_room_rack3d_contract(db_session):
    room_id = await _seed(db_session, "京C区", "RM-01-03", "4楼", [{
        "name": "机柜01", "code": "RM-01-03-01", "total_units": 42,
        "available_units": 39, "rated_power": 10,
        "devices": [
            {"name": "sw-01", "asset_number": "AST001", "start_u": 1, "end_u": 1,
             "power_rating": 0.5, "management_ip": "10.0.0.1"},
            {"name": "srv-01", "asset_number": "AST002", "start_u": 3, "end_u": 6, "power_rating": 2.0},
        ],
    }])
    data = await room_rack3d(room_id, db=db_session, _current_user=_FakeUser())

    assert data["room"]["name"] == "京C区"
    assert data["room"]["floor"] == "4楼"
    assert len(data["racks"]) == 1
    rk = data["racks"][0]
    assert rk["code"] == "RM-01-03-01"
    assert rk["total_units"] == 42
    assert rk["utilization"] == 7                       # (42-39)/42 = 7%
    assert rk["power_load"] == pytest.approx(2.5, abs=0.01)
    assert rk["power_load_pct"] == pytest.approx(25, abs=0.01)
    assert rk["device_count"] == 2
    devs = {d["name"]: d for d in rk["devices"]}
    assert devs["sw-01"]["start_u"] == 1 and devs["sw-01"]["end_u"] == 1
    assert devs["srv-01"]["start_u"] == 3 and devs["srv-01"]["end_u"] == 6
    assert devs["sw-01"]["management_ip"] == "10.0.0.1"
    assert "temperature" in data and "sensors" in data and "rack_alerts" in data


@pytest.mark.asyncio
async def test_region_switch_data_isolation(db_session):
    a_id = await _seed(db_session, "京A", "RM-A", "1楼", [{
        "name": "A-R01", "code": "RM-A-01",
        "devices": [{"name": "dev-京A", "asset_number": "AST-A", "start_u": 1, "end_u": 1}],
    }])
    b_id = await _seed(db_session, "京B", "RM-B", "1楼", [{
        "name": "B-R01", "code": "RM-B-01",
        "devices": [{"name": "dev-京B", "asset_number": "AST-B", "start_u": 2, "end_u": 2}],
    }])

    a = await room_rack3d(a_id, db=db_session, _current_user=_FakeUser())
    b = await room_rack3d(b_id, db=db_session, _current_user=_FakeUser())

    assert [r["code"] for r in a["racks"]] == ["RM-A-01"]
    assert [r["code"] for r in b["racks"]] == ["RM-B-01"]
    a_devs = {d["name"] for r in a["racks"] for d in r["devices"]}
    assert a_devs == {"dev-京A"}
    assert "dev-京B" not in a_devs


@pytest.mark.asyncio
async def test_room_rack3d_not_found(db_session):
    with pytest.raises(HTTPException) as exc:
        await room_rack3d(99999, db=db_session, _current_user=_FakeUser())
    assert exc.value.status_code == 404
