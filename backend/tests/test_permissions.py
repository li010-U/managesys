"""RBAC ???????

?? require_permission ????????
- ???????????
- ?????????????
- ???????? 403?
- ??????? token?? get_current_user ?? 401?
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException

from app.core.deps import require_permission, require_any_permission, has_permission


class FakePermission:
    def __init__(self, code: str):
        self.code = code


class FakeRole:
    def __init__(self, codes):
        self.permissions = [FakePermission(c) for c in codes]


class FakeUser:
    def __init__(self, is_super_admin: bool = False, roles=None):
        self.is_super_admin = is_super_admin
        self.roles = roles or []
        self.is_active = True


async def _call(permission_code, user):
    checker = require_permission(permission_code)
    # ?????? current_user??? get_current_user ??
    return await checker(user)


@pytest.mark.asyncio
async def test_super_admin_bypasses():
    user = FakeUser(is_super_admin=True)
    result = await _call("device:delete", user)
    assert result is user


@pytest.mark.asyncio
async def test_user_with_permission_passes():
    user = FakeUser(roles=[FakeRole(["device:view", "device:create"])])
    result = await _call("device:create", user)
    assert result is user


@pytest.mark.asyncio
async def test_user_without_permission_forbidden():
    user = FakeUser(roles=[FakeRole(["device:view"])])
    with pytest.raises(HTTPException) as exc:
        await _call("device:delete", user)
    assert exc.value.status_code == 403
    assert "device:delete" in exc.value.detail


@pytest.mark.asyncio
async def test_user_with_no_roles_forbidden():
    user = FakeUser(roles=[])
    with pytest.raises(HTTPException) as exc:
        await _call("room:create", user)
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_any_permission_from_multiple_roles():
    # ???????????
    user = FakeUser(roles=[FakeRole(["room:view"]), FakeRole(["monitor:handle_alert"])])
    result = await _call("monitor:handle_alert", user)
    assert result is user


# ===== require_any_permission =====

async def _call_any(codes, user):
    checker = require_any_permission(*codes)
    return await checker(user)


@pytest.mark.asyncio
async def test_any_permission_super_admin_bypasses():
    user = FakeUser(is_super_admin=True)
    assert (await _call_any(["device:mount", "device:unmount"], user)) is user


@pytest.mark.asyncio
async def test_any_permission_with_one_match_passes():
    user = FakeUser(roles=[FakeRole(["device:view", "device:mount"])])
    assert (await _call_any(["device:mount", "device:unmount"], user)) is user


@pytest.mark.asyncio
async def test_any_permission_no_match_forbidden():
    user = FakeUser(roles=[FakeRole(["device:view"])])
    with pytest.raises(HTTPException) as exc:
        await _call_any(["device:mount", "device:unmount"], user)
    assert exc.value.status_code == 403


# ===== has_permission =====

async def test_has_permission_true_for_holder():
    user = FakeUser(roles=[FakeRole(["system:view"])])
    assert has_permission(user, "system:view") is True


async def test_has_permission_false_for_nonholder():
    user = FakeUser(roles=[FakeRole(["system:view"])])
    assert has_permission(user, "system:create") is False


async def test_has_permission_true_for_super_admin():
    user = FakeUser(is_super_admin=True)
    assert has_permission(user, "anything:xyz") is True
