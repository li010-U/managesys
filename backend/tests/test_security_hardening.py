# -*- coding: utf-8 -*-
"""新增安全加固的回归测试。
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import HTTPException

from app.core.security import create_access_token, decode_access_token, hash_password, verify_password
from app.core.deps import get_current_user, require_permission


def test_token_carries_version_and_decodes_roundtrip():
    token = create_access_token(data={"sub": "7"}, token_version=3)
    payload = decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == "7"
    assert payload["ver"] == 3


def test_decode_rejects_garbage():
    assert decode_access_token("not-a-token") is None


def test_hash_verify_password():
    h = hash_password("Abc12345!@#")
    assert verify_password("Abc12345!@#", h)
    assert not verify_password("wrong", h)


@pytest.mark.asyncio
async def test_get_current_user_rejects_outdated_token_version():
    from app.core import deps
    user = MagicMock()
    user.id = 1
    user.is_active = True
    user.token_version = 5

    # 用户当前 token_version=5，但令牌携带 ver=4（旧令牌）
    token = create_access_token(data={"sub": "1"}, token_version=4)
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute.return_value = result

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_valid_version_passes():
    user = MagicMock()
    user.id = 1
    user.is_active = True
    user.token_version = 5

    token = create_access_token(data={"sub": "1"}, token_version=5)
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute.return_value = result

    got = await get_current_user(token=token, db=db)
    assert got is user


@pytest.mark.asyncio
async def test_get_current_user_rejects_non_numeric_sub():
    db = AsyncMock()
    token = create_access_token(data={"sub": "abc"}, token_version=0)
    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(token=token, db=db)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_assistant_requires_dashboard_permission():
    user = MagicMock()
    user.is_super_admin = False
    user.roles = [MagicMock(permissions=[MagicMock(code="device:view")])]

    checker = require_permission("monitor:view_dashboard")
    with pytest.raises(HTTPException) as exc_info:
        await checker(user)
    assert exc_info.value.status_code == 403


def _run_security_check(debug, enforce, secret):
    """在给定配置下调用 _check_security_config()，返回是否抛出 RuntimeError。"""
    import app.main as m
    orig = (m.settings.DEBUG, m.settings.ENFORCE_SECURITY, m.settings.SECRET_KEY)
    m.settings.DEBUG = debug
    m.settings.ENFORCE_SECURITY = enforce
    m.settings.SECRET_KEY = secret
    try:
        m._check_security_config()
    except RuntimeError:
        return True
    finally:
        m.settings.DEBUG, m.settings.ENFORCE_SECURITY, m.settings.SECRET_KEY = orig
    return False


def test_enforce_security_blocks_weak_debug():
    # 生产准入开启 + DEBUG=true -> 拒绝启动
    assert _run_security_check(debug=True, enforce=True,
                               secret="a-real-strong-secret-key-value") is True


def test_enforce_security_blocks_default_secret():
    # 生产准入开启 + 默认 SECRET_KEY -> 拒绝启动
    assert _run_security_check(debug=False, enforce=True,
                               secret="dev-secret-key-change-in-production-2024") is True


def test_enforce_security_ok_when_hardened():
    # 生产准入开启 + 配置已加固（DEBUG=false、非默认密钥）-> 不拒绝
    assert _run_security_check(debug=False, enforce=True,
                               secret="a-real-strong-secret-key-value") is False


def test_enforce_security_off_only_warns():
    # 未开启生产准入 + 弱配置 -> 仅警告、不拒绝（兼容开发模式）
    assert _run_security_check(debug=True, enforce=False,
                               secret="dev-secret-key-change-in-production-2024") is False
