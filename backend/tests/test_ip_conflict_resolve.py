# -*- coding: utf-8 -*-
"""IP ???????conflicts ????? + ?? resolve ??? ?????"""
import pytest
import pytest_asyncio

from sqlalchemy import select
from app.services.ip_resource_service import IpResourceService
from app.models.device import Device
from app.models.device_type import DeviceType


async def _mk_device(db, device_type_id, name, ast_no, mgmt=None, biz=None, oob=None):
    d = Device(
        device_type_id=device_type_id, name=name, asset_number=ast_no,
        management_ip=mgmt, business_ip=biz, out_of_band_ip=oob, status="running",
    )
    db.add(d)
    await db.flush()
    return d


async def _mk_type(db, name, code):
    t = DeviceType(name=name, code=code, category="server")
    db.add(t)
    await db.flush()
    return t


@pytest.mark.asyncio
async def test_conflicts_detects_explicit_and_potential(db_session):
    t = await _mk_type(db_session, "t-ip", "tip")
    await _mk_device(db_session, t.id, "d1", "A001", mgmt="10.0.0.1")
    await _mk_device(db_session, t.id, "d2", "A002", mgmt="10.0.0.1", biz="10.0.0.1")
    await db_session.commit()

    svc = IpResourceService(db_session)
    data = await svc.conflicts()
    # 10.0.0.1 ? management ???? = ????
    # 10.0.0.1 ??? management ? business = ????
    assert data["total"] >= 2
    explicit_ips = {c["ip"] for c in data["explicit"]}
    assert "10.0.0.1" in explicit_ips
    pot_ips = {c["ip"] for c in data["potential"]}
    assert "10.0.0.1" in pot_ips


@pytest.mark.asyncio
async def test_resolve_conflict_changes_field_and_audits(db_session):
    from app.services.audit_service import AuditService
    t = await _mk_type(db_session, "t-ip2", "tip2")
    d1 = await _mk_device(db_session, t.id, "d1", "A003", mgmt="10.0.0.5")
    await _mk_device(db_session, t.id, "d2", "A004", mgmt="10.0.0.5")
    await db_session.commit()

    svc = IpResourceService(db_session)
    res = await svc.resolve_conflict(
        d1.id, "management", "10.0.0.99",
        operator_username="admin", operator_ip="1.2.3.4",
    )
    assert res["new_ip"] == "10.0.0.99"
    assert res["old_ip"] == "10.0.0.5"

    # ???????
    got = (await db_session.execute(select(Device).where(Device.id == d1.id))).scalar_one()
    # ???????????? IP
    assert "10.0.0.99" in (got.management_ip or "")

    # ???????
    logs = await AuditService(db_session).get_audit_logs(action="ip_conflict_resolve")
    assert logs[1] >= 1

    # ???????d1 ??? .99??? d2 ? .5 ?????
    after = await svc.conflicts()
    assert after["total"] < 2


@pytest.mark.asyncio
async def test_resolve_rejects_invalid_ip(db_session):
    t = await _mk_type(db_session, "t-ip3", "tip3")
    d1 = await _mk_device(db_session, t.id, "d1", "A005", mgmt="10.0.0.10")
    await db_session.commit()
    svc = IpResourceService(db_session)
    with pytest.raises(ValueError):
        await svc.resolve_conflict(d1.id, "management", "not-an-ip")


@pytest.mark.asyncio
async def test_resolve_rejects_unknown_role(db_session):
    t = await _mk_type(db_session, "t-ip4", "tip4")
    d1 = await _mk_device(db_session, t.id, "d1", "A006", mgmt="10.0.0.11")
    await db_session.commit()
    svc = IpResourceService(db_session)
    with pytest.raises(ValueError):
        await svc.resolve_conflict(d1.id, "bogus", "10.0.0.1")
