# -*- coding: utf-8 -*-
"""VLAN \u5b9e\u4f53 / \u5b50\u7f51\u5173\u8054 / \u6c34\u4f4d\u6807\u8bb0 / CSV \u5bfc\u51fa \u56de\u5f52\u6d4b\u8bd5\u3002"""
import pytest
from sqlalchemy import select, func
from app.services.ip_registry_service import IpRegistryService
from app.models.vlan import Vlan
from app.models.facility import DataCenter, Room
from app.models.ip_address import IpAddress, IpSubnet


async def _mk_room(db):
    dc = DataCenter(name="DC", code="DCX", status="active")
    db.add(dc)
    await db.flush()
    room = Room(name="R1", code="R-01", data_center_id=dc.id, floor="1F")
    db.add(room)
    await db.flush()
    return room


@pytest.mark.asyncio
async def test_vlan_crud_and_duplicate(db_session):
    svc = IpRegistryService(db_session)
    v = await svc.create_vlan(100, "\u7ba1\u7406\u7f51", None, None)
    assert v.id is not None
    with pytest.raises(ValueError):
        await svc.create_vlan(100, "dup")
    await svc.update_vlan(v.id, name="\u4e1a\u52a1\u7f51")
    v2 = (await db_session.execute(select(Vlan).where(Vlan.id == v.id))).scalar_one()
    assert v2.name == "\u4e1a\u52a1\u7f51"
    lst = await svc.list_vlans()
    assert len(lst) == 1
    assert lst[0]["vlan_id"] == 100
    assert await svc.delete_vlan(v.id) is True


@pytest.mark.asyncio
async def test_subnet_vlan_room_and_watermark(db_session):
    svc = IpRegistryService(db_session)
    room = await _mk_room(db_session)
    v = await svc.create_vlan(200, "vm", None, room.id)
    sub = await svc.create_subnet(name="s", network="10.81.0.0", prefix=24, vlan_id=v.id)
    # 分\u914d\u51e0\u4e2a\u5730\u5740\u4f7f\u7528\u7387\u8fbe\u5230\u6c34\u4f4d\u4ee5\u4e0a\uff08254\u53ef\u7528\uff0c\u5206\u914d 210 \u4e2a > 80%\uff09
    for i in range(1, 211):
        await svc.save_address(f"10.81.0.{i}", "allocated", subnet_id=sub.id)
    await db_session.flush()
    subs = await svc.list_subnets()
    s = next(x for x in subs if x["id"] == sub.id)
    assert s["vlan_id"] == v.id
    assert s["vlan_name"] is not None
    assert s["room_id"] == room.id
    assert s["room_name"] == "R1"
    assert s["over_watermark"] is True
    vlans = await svc.list_vlans()
    vl = next(x for x in vlans if x["id"] == v.id)
    assert vl["subnet_count"] == 1
    assert vl["over_watermark"] is True
    assert vl["room_name"] == "R1"


@pytest.mark.asyncio
async def test_delete_vlan_clears_subnet_link(db_session):
    svc = IpRegistryService(db_session)
    v = await svc.create_vlan(300, "x")
    sub = await svc.create_subnet(name="s", network="10.82.0.0", prefix=24, vlan_id=v.id)
    assert sub.vlan_id == v.id
    await svc.delete_vlan(v.id)
    await db_session.flush()
    sub2 = (await db_session.execute(select(IpSubnet).where(IpSubnet.id == sub.id))).scalar_one()
    assert sub2.vlan_id is None


@pytest.mark.asyncio
async def test_export_csv(db_session):
    svc = IpRegistryService(db_session)
    await svc.create_subnet(name="a", network="10.83.0.0", prefix=24)
    csv_s = await svc.export_subnets_csv()
    assert "CIDR" in csv_s
    assert "10.83.0.0/24" in csv_s
    csv_a = await svc.export_addresses_csv()
    assert "IP" in csv_a
