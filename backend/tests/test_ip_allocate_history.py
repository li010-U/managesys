# -*- coding: utf-8 -*-
"""位于担保的 IP 自动分配 / 分配前防冲突 / 台账变更历史 回归测试。"""
import pytest
from sqlalchemy import select

from app.services.ip_registry_service import (
    IpRegistryService, sync_device_ip_ledger, validate_no_conflict,
)
from app.models.ip_address import IpAddress, IpAddressHistory
from app.models.device import Device
from app.models.device_type import DeviceType


async def _mk_type(db, code="SRV2"):
    t = (await db.execute(select(DeviceType).where(DeviceType.code == code))).scalar_one_or_none()
    if t is None:
        t = DeviceType(name="server", code=code, category="server")
        db.add(t)
        await db.flush()
    return t


@pytest.mark.asyncio
async def test_allocate_ip_picks_free_and_skips_gateway(db_session):
    svc = IpRegistryService(db_session)
    sub = await svc.create_subnet(name="n", network="10.77.0.0", prefix=24, gateway="10.77.0.254")
    t = await _mk_type(db_session)
    dev = Device(name="dA", asset_number="AL-1", device_type_id=t.id, status="running")
    db_session.add(dev)
    await db_session.flush()

    r = await svc.allocate_ip(sub.id, "management", dev.id)
    assert r["subnet_id"] == sub.id
    assert r["used_as"] == "management"
    # 应避开网络地址 .0 和网关 .254，选择最小空闲
    assert r["address"] == "10.77.0.1"
    rows = (await db_session.execute(
        select(IpAddress).where(IpAddress.subnet_id == sub.id))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "allocated"
    assert rows[0].device_id == dev.id
    # 历史应被写入
    hist = (await db_session.execute(
        select(IpAddressHistory).where(IpAddressHistory.address == "10.77.0.1"))).scalars().all()
    assert len(hist) == 1
    assert hist[0].source == "allocate"


@pytest.mark.asyncio
async def test_validate_no_conflict_rejects_occupied(db_session):
    svc = IpRegistryService(db_session)
    t = await _mk_type(db_session)
    d1 = Device(name="d1", asset_number="C-1", device_type_id=t.id, status="running")
    db_session.add(d1)
    await db_session.flush()
    await svc.save_address("10.78.0.5", "allocated", device_id=d1.id)
    await db_session.flush()
    d2 = Device(name="d2", asset_number="C-2", device_type_id=t.id, status="running")
    db_session.add(d2)
    await db_session.flush()
    with pytest.raises(ValueError):
        await validate_no_conflict(db_session, "10.78.0.5")
    # 但对同一设备本身不算冲突
    ok = await validate_no_conflict(db_session, "10.78.0.5", exclude_device_id=d1.id)
    assert ok is None


@pytest.mark.asyncio
async def test_device_sync_does_not_steal_occupied_ip(db_session):
    t = await _mk_type(db_session)
    svc = IpRegistryService(db_session)
    await svc.create_subnet(name="n", network="10.79.0.0", prefix=24)
    d1 = Device(name="d1", asset_number="S-1", device_type_id=t.id, status="running",
                management_ip="10.79.0.10")
    db_session.add(d1)
    await db_session.flush()
    await sync_device_ip_ledger(db_session, d1)
    d2 = Device(name="d2", asset_number="S-2", device_type_id=t.id, status="running",
                management_ip="10.79.0.10")
    db_session.add(d2)
    await db_session.flush()
    res = await sync_device_ip_ledger(db_session, d2)
    assert res["conflict"] == 1
    # 盖不应抢走，仍归属 d1
    row = (await db_session.execute(
        select(IpAddress).where(IpAddress.address == "10.79.0.10"))).scalar_one()
    assert row.device_id == d1.id


@pytest.mark.asyncio
async def test_history_records_save_address_change(db_session):
    svc = IpRegistryService(db_session)
    t = await _mk_type(db_session)
    d1 = Device(name="d1", asset_number="H-1", device_type_id=t.id, status="running")
    db_session.add(d1)
    await db_session.flush()
    await svc.save_address("10.80.0.5", "allocated", device_id=d1.id, operator="tester")
    await db_session.flush()
    hist = (await db_session.execute(
        select(IpAddressHistory).where(IpAddressHistory.address == "10.80.0.5"))).scalars().all()
    assert len(hist) == 1
    assert hist[0].operator == "tester"
