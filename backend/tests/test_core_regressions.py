# -*- coding: utf-8 -*-
"""核心主链路回归测试：针对本轮修复的两个“线上炸”。
1) GET 只读接口 /rooms/{id} 必须 200（防止审计引用未定义变量导致 500、导致 3D 加载失败）；
2) 账户被锁定时登录返回 401 而非 500（防止时区 naive/aware 比较 TypeError）。
"""
from starlette.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def _login_ok(client) -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"username": "admin", "password": "Pytest-Admin-12345"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_room_detail_get_returns_200():
    with TestClient(app) as client:
        h = _login_ok(client)
        # 创建 dc -> room，确保存在可检索的机房
        dc = client.post("/api/v1/facilities/data-centers",
                         json={"name": "CR-DC", "code": "CRDC", "status": "active"}, headers=h)
        assert dc.status_code == 201, dc.text
        room = client.post("/api/v1/facilities/rooms",
                           json={"data_center_id": dc.json()["id"], "name": "CR-Room",
                                 "code": "CR-RM", "floor": "1F"}, headers=h)
        assert room.status_code == 201, room.text
        rid = room.json()["id"]
        # 关键：GET 只读接口必须 200（之前因审计 NameError 返回 500）
        r = client.get(f"/api/v1/facilities/rooms/{rid}", headers=h)
        assert r.status_code == 200, r.text
        # 3D 场景接口也应 200
        r3 = client.get(f"/api/v1/facilities/rooms/{rid}/rack3d", headers=h)
        assert r3.status_code == 200, r3.text


def test_locked_account_login_returns_401_not_500():
    from app.db.session import async_session_factory
    from app.models.user import User
    from sqlalchemy import select
    import asyncio
    from datetime import datetime, timedelta, timezone

    # 先在磁停库里将 admin 锁定（设置 locked_until）
    async def lock():
        async with async_session_factory() as db:
            u = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
            u.locked_until = datetime.now(timezone.utc) + timedelta(hours=1)
            await db.commit()
    asyncio.run(lock())

    try:
        with TestClient(app) as client:
            r = client.post("/api/v1/auth/login",
                            json={"username": "admin", "password": "Pytest-Admin-12345"})
            # 被锁定 -> 应返回 401/403（不能是 500）
            assert r.status_code in (401, 403), r.text
    finally:
        # 恢复 admin 状态，避免影响同一 temp 库的其他测试
        async def unlock():
            async with async_session_factory() as db:
                u = (await db.execute(select(User).where(User.username == "admin"))).scalar_one()
                u.locked_until = None
                u.login_attempts = 0
                await db.commit()
        asyncio.run(unlock())
