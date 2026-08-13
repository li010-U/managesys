# -*- coding: utf-8 -*-
"""IP 台账与子网管理测试。

覆盖高频回归点：
- 子网 CRUD / 重复检测 / CIDR 校验
- 地址台账登记 / 超出子网拒绝 / 分页
- 设备IP自动同步（唯一事实源：设备建/改/删同步台账）
"""
import pytest
from sqlalchemy import select

from app.services.ip_registry_service import IpRegistryService, sync_device_ip_ledger, release_device_ip_ledger
from app.models.ip_address import IpAddress
from app.models.device import Device
from app.models.device_type import DeviceType


async def _mk_type(db, code="SRV"):
    t = (await db.execute(select(DeviceType).where(DeviceType.code == code))).scalar_one_or_none()
    if t is None:
        t = DeviceType(name="server", code=code, category="server")
        db.add(t)
        await db.flush()
    return t


@pytest.mark.asyncio
async def test_subnet_crud_and_duplicate(db_session):
    svc = IpRegistryService(db_session)
    sub = await svc.create_subnet(name="管理网段", network="10.76.121.0", prefix=24,
                                  gateway="10.76.121.1", vlan="10")
    assert sub.id is not None
    assert sub.network == "10.76.121.0"
    with pytest.raises(ValueError):
        await svc.create_subnet(name="重复", network="10.76.121.0", prefix=24)
    updated = await svc.update_subnet(sub.id, name="管理网段v2", gateway="10.76.121.254")
    assert updated.gateway == "10.76.121.254"
    subs = await svc.list_subnets()
    assert len(subs) == 1
    assert subs[0]["cidr"] == "10.76.121.0/24"
    assert subs[0]["capacity"] == 256
    assert await svc.delete_subnet(sub.id) is True
    assert len(await svc.list_subnets()) == 0


@pytest.mark.asyncio
async def test_save_address_validates_subnet_membership(db_session):
    svc = IpRegistryService(db_session)
    await svc.create_subnet(name="网段", network="10.76.121.0", prefix=24)
    row = await svc.save_address("10.76.121.99", "reserved", subnet_id=1, remark="预留")
    assert row.subnet_id == 1
    assert row.status == "reserved"
    with pytest.raises(ValueError):
        await svc.save_address("192.168.1.1", "allocated", subnet_id=1)
    items, total = await svc.list_addresses(subnet_id=1, page=1, page_size=10)
    assert total == 1
    assert items[0]["address"] == "10.76.121.99"


@pytest.mark.asyncio
async def test_device_ip_auto_sync_create_update_delete(db_session):
    t = await _mk_type(db_session)
    svc = IpRegistryService(db_session)
    sub = await svc.create_subnet(name="网段", network="10.76.121.0", prefix=24)

    dev = Device(name="d1", asset_number="A1", device_type_id=t.id, status="running",
                 management_ip="10.76.121.10", business_ip="10.76.121.11,10.76.121.12",
                 out_of_band_ip="10.76.121.200")
    db_session.add(dev)
    await db_session.flush()
    await sync_device_ip_ledger(db_session, dev)

    rows = {r.address: r for r in (await db_session.execute(
        select(IpAddress).where(IpAddress.device_id == dev.id))).scalars().all()}
    assert set(rows) == {"10.76.121.10", "10.76.121.11", "10.76.121.12", "10.76.121.200"}
    assert all(r.status == "allocated" for r in rows.values())
    assert rows["10.76.121.11"].used_as == "business"
    assert rows["10.76.121.200"].used_as == "oob"
    assert rows["10.76.121.10"].subnet_id == sub.id

    dev.management_ip = "10.76.121.99"
    dev.business_ip = "10.76.121.11"
    await sync_device_ip_ledger(db_session, dev)
    alloc = {r.address: r for r in (await db_session.execute(
        select(IpAddress).where(IpAddress.status == "allocated"))).scalars().all()}
    assert set(alloc) == {"10.76.121.99", "10.76.121.11", "10.76.121.200"}
    freed = {r.address: r for r in (await db_session.execute(
        select(IpAddress).where(IpAddress.status == "free"))).scalars().all()}
    assert "10.76.121.10" in freed and freed["10.76.121.10"].device_id is None
    assert "10.76.121.12" in freed and freed["10.76.121.12"].device_id is None

    await release_device_ip_ledger(db_session, dev.id)
    remaining = (await db_session.execute(
        select(IpAddress).where(IpAddress.device_id == dev.id))).scalars().all()
    assert remaining == []
    freed2 = {r.address: r for r in (await db_session.execute(
        select(IpAddress).where(IpAddress.status == "free"))).scalars().all()}
    assert "10.76.121.99" in freed2


@pytest.mark.asyncio
async def test_device_service_wiring_syncs_ledger(db_session):
    from app.services.device_service import DeviceService
    from app.schemas.device import DeviceCreate, DeviceUpdate
    from app.services.ip_registry_service import IpRegistryService
    t = await _mk_type(db_session)
    await IpRegistryService(db_session).create_subnet(name="sub1", network="10.99.0.0", prefix=24)

    svc = DeviceService(db_session)
    dev = await svc.create(DeviceCreate(name="d2", asset_number="A2", device_type_id=t.id,
                     status="running", management_ip="10.99.0.10", business_ip="10.99.0.11", out_of_band_ip="10.99.0.200"))
    assert dev.id is not None
    rows = {r.address for r in (await db_session.execute(
        select(IpAddress).where(IpAddress.device_id == dev.id))).scalars().all()}
    assert rows == {"10.99.0.10", "10.99.0.11", "10.99.0.200"}

    await svc.update(dev.id, DeviceUpdate(management_ip="10.99.0.99", business_ip="10.99.0.11"))
    held = {r.address for r in (await db_session.execute(
        select(IpAddress).where(IpAddress.device_id == dev.id))).scalars().all()}
    assert held == {"10.99.0.99", "10.99.0.11", "10.99.0.200"}
    freed = {r.address for r in (await db_session.execute(
        select(IpAddress).where(IpAddress.status == "free"))).scalars().all()}
    assert "10.99.0.10" in freed

    await svc.delete(dev.id)
    held2 = (await db_session.execute(
        select(IpAddress).where(IpAddress.device_id == dev.id))).scalars().all()
    assert held2 == []
