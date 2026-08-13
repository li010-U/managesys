# -*- coding: utf-8 -*-
"""\u3010\u7b2c\uff15\u9879\u3011AI \u5e95\u5ea7\u6570\u636e\u771f\u5b9e\u6027\uff1a\u5feb\u7167\u542b\u5b9e\u6d4b\u529f\u7387\u6570\u636e + \u6570\u636e\u8d28\u91cf\u6807\u8bb0"""
import pytest
from app.services.assistant_service import AssistantService
from app.models.facility import DataCenter, Room, Rack
from app.models.device import Device
from app.models.device_type import DeviceType


async def _seed(db, rated_power=10.0, devices=(), available_units=40):
    dc = DataCenter(name="DC", code="DC1")
    db.add(dc); await db.flush()
    t = DeviceType(name="server", code="SRV", category="server")
    db.add(t); await db.flush()
    room = Room(data_center_id=dc.id, name="A", code="RM-A", floor="1", area=50)
    db.add(room); await db.flush()
    rack = Rack(room_id=room.id, name="R1", code="RM-A-01", total_units=42,
                available_units=available_units, rated_power=rated_power)
    db.add(rack); await db.flush()
    for i, (status, pr) in enumerate(devices):
        db.add(Device(name=f"d{i}", asset_number=f"A{i}", device_type_id=t.id, rack_id=rack.id,
                      start_u=1 + i, end_u=1 + i, status=status, power_rating=pr))
    await db.flush()
    return rack.id


@pytest.mark.asyncio
async def test_snapshot_power_fields_present(db_session):
    # \u4e00\u53f0\u6b63\u5728\u8fd0\u884c (3kW) + \u4e00\u53f0\u5e93\u5b58 (10kW \u4e0d\u8ba1\u5165)
    await _seed(db_session, rated_power=10.0, devices=[("running", 3.0), ("in_stock", 10.0)])
    svc = AssistantService(db_session)
    snap = await svc.build_snapshot()

    power = snap["power"]
    assert power["power_load_kw"] == pytest.approx(3.0, abs=0.01)  # \u5e93\u5b58\u4e0d\u7edf\u8ba1
    assert power["rated_power_kw"] == pytest.approx(10.0, abs=0.01)
    assert power["power_util_pct"] == pytest.approx(30.0, abs=0.1)
    assert power["loads_kw"]["RM-A-01"] == pytest.approx(3.0, abs=0.01)
    # \u6570\u636e\u5145\u8db3,\u4e0d\u6807\u8bb0\u7f3a\u5931
    dq = snap["data_quality"]
    assert dq.get("power_data_missing") is None
    assert dq.get("rated_power_missing") is None


@pytest.mark.asyncio
async def test_snapshot_power_missing_data_quality(db_session):
    # \u6ca1\u6709\u8bbe\u5907\u529f\u7387,\u4e14\u989d\u5b9a\u529f\u7387\u4e3a0 -> \u6807\u8bb0\u6570\u636e\u7f3a\u5931
    await _seed(db_session, rated_power=None, devices=[])
    svc = AssistantService(db_session)
    snap = await svc.build_snapshot()

    dq = snap["data_quality"]
    assert dq.get("rated_power_missing") is True
    assert dq.get("power_util_unreliable") is True
    power = snap["power"]
    assert power["rated_power_kw"] == 0.0
    assert power["power_util_pct"] == 0.0


@pytest.mark.asyncio
async def test_snapshot_rack_high_includes_power(db_session):
    # \u4e00\u53f0\u8fdb\u884c\u4e2d 8kW (\u5229\u7528\u7387 >80%)\uff0c\u9ad8\u5360\u7528\u5217\u8868\u5e26\u529f\u7387\uff1a10/12=83.3%
    await _seed(db_session, rated_power=12.0, devices=[("running", 8.0)], available_units=2)
    svc = AssistantService(db_session)
    snap = await svc.build_snapshot()
    high = snap["high_usage_racks"]
    assert high
    row = high[0]
    assert row["power_load_kw"] == pytest.approx(8.0, abs=0.01)
    assert row["power_util_pct"] == pytest.approx(66.7, abs=0.5)
