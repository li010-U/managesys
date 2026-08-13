# -*- coding: utf-8 -*-
"""Power aggregation tests: supply load no longer reports 0 when rated power is missing."""
import pytest
from app.services.insight_service import InsightService
from app.models.facility import DataCenter, Room, Rack
from app.models.device import Device
from app.models.device_type import DeviceType


@pytest.mark.asyncio
async def test_rack_capacity_power_not_zero(db_session):
    dc = DataCenter(name="DC", code="DC1")
    db_session.add(dc); await db_session.flush()
    t = DeviceType(name="server", code="SRV", category="server")
    db_session.add(t); await db_session.flush()
    room = Room(data_center_id=dc.id, name="A", code="RM-A", floor="1", area=50)
    db_session.add(room); await db_session.flush()
    rack = Rack(room_id=room.id, name="R1", code="RM-A-01", total_units=42, available_units=38, rated_power=10)
    db_session.add(rack); await db_session.flush()
    db_session.add(Device(name="srv", asset_number="X", device_type_id=t.id, rack_id=rack.id,
                         start_u=1, end_u=3, status="running", power_rating=3.0))
    db_session.add(Device(name="off", asset_number="Y", device_type_id=t.id, rack_id=rack.id,
                         start_u=4, end_u=4, status="offline", power_rating=5.0))
    await db_session.flush()

    data = await InsightService(db_session).rack_capacity(room_id=room.id)
    assert data["count"] == 1
    r = data["racks"][0]
    assert r["power_used_kw"] == pytest.approx(3.0, abs=0.01)
    assert r["rated_power_kw"] == 10.0
    assert r["power_util_pct"] == pytest.approx(30.0, abs=0.1)


@pytest.mark.asyncio
async def test_rack_capacity_missing_rated_power_fallback(db_session):
    dc = DataCenter(name="DC", code="DC1")
    db_session.add(dc); await db_session.flush()
    t = DeviceType(name="server", code="SRV", category="server")
    db_session.add(t); await db_session.flush()
    room = Room(data_center_id=dc.id, name="A", code="RM-A", floor="1", area=50)
    db_session.add(room); await db_session.flush()
    rack = Rack(room_id=room.id, name="R1", code="RM-A-01", total_units=42, available_units=40, rated_power=None)
    db_session.add(rack); await db_session.flush()
    db_session.add(Device(name="srv", asset_number="X", device_type_id=t.id, rack_id=rack.id,
                         start_u=1, end_u=2, status="mounted", power_rating=2.0))
    await db_session.flush()

    data = await InsightService(db_session).rack_capacity(room_id=room.id)
    r = data["racks"][0]
    assert r["power_used_kw"] == pytest.approx(2.0, abs=0.01)
    assert r["power_util_pct"] == pytest.approx(20.0, abs=0.1)