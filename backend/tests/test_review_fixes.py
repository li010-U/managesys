# -*- coding: utf-8 -*-
"""审查修复复归测试：逻辑敏感改动的固化。"""
import pytest

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.services.device_service import DeviceService, ALLOWED_DEVICE_STATUSES
from app.services.user_service import UserService
from app.services.ip_registry_service import IpRegistryService
from app.models.ip_address import IpAddress
from app.models.device import Device
from app.models.device_type import DeviceType
from app.models.user import User
from app.models.role import Role
from app.schemas.user import UserUpdateRequest


async def _mk_type(db, name, code):
    t = DeviceType(name=name, code=code, category="server")
    db.add(t)
    await db.flush()
    return t


async def _mk_device(db, t, name, ast_no):
    d = Device(device_type_id=t.id, name=name, asset_number=ast_no, status="mounted")
    db.add(d)
    await db.flush()
    return d


async def _mk_admin(db, username):
    from app.core.security import hash_password
    role = (await db.execute(select(Role).where(Role.code == "super_admin"))).scalar_one_or_none()
    u = User(username=username, hashed_password=hash_password("StrongPass-123"), is_active=True, is_super_admin=True)
    if role:
        u.roles = [role]
    db.add(u)
    await db.flush()
    return u


@pytest.mark.asyncio
async def test_ip_address_global_unique_rejects_duplicate(db_session):
    """#1: 同一 address 不允许重复（包括 subnet_id 为 NULL）。"""
    db_session.add(IpAddress(address="10.9.9.9", status="allocated"))
    await db_session.flush()
    db_session.add(IpAddress(address="10.9.9.9", status="free"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


@pytest.mark.asyncio
async def test_change_status_rejects_invalid_status(db_session):
    """#5: 设备状态白名单，非法状态拒绝。"""
    t = await _mk_type(db_session, "t-rf", "trf")
    d = await _mk_device(db_session, t, "d", "A-RF1")
    await db_session.commit()
    svc = DeviceService(db_session)
    with pytest.raises(ValueError):
        await svc.change_status(d.id, "hacked-status", operator_username="op")


@pytest.mark.asyncio
async def test_change_status_accepts_valid_status(db_session):
    """#5: 合法状态可通过。"""
    t = await _mk_type(db_session, "t-rf2", "trf2")
    d = await _mk_device(db_session, t, "d", "A-RF2")
    await db_session.commit()
    svc = DeviceService(db_session)
    nd = await svc.change_status(d.id, "offline", operator_username="op")
    assert nd is not None and nd.status == "offline"


@pytest.mark.asyncio
async def test_removing_last_active_super_admin_blocked(db_session):
    """#13: 移除最后一个有效超管会被拒绝。"""
    # 用一个权限完整的超管
    admin = await _mk_admin(db_session, "soleadmin")
    # 确保只有这一个超管
    other = (await db_session.execute(select(User).where(User.is_super_admin == True))).scalars().all()  # noqa: E712
    # 只保留当前超管（测试基竟数据可能未创建超管角色，已在上面创建）
    svc = UserService(db_session)
    req = UserUpdateRequest(is_active=False)
    with pytest.raises(ValueError):
        await svc.update_user(admin.id, req, operator_username="admin")
