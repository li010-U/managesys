# -*- coding: utf-8 -*-
"""告警生命周期（自动恢复/去重防抖/偶发故障）与环境关联统计回归测试。"""
from datetime import datetime, timedelta

import pytest

from app.models.alert import Alert
from app.models.env_weather import EnvWeatherRecord, TransientFailureEvent
from app.services.alert_lifecycle_service import AlertLifecycleService
from app.services.environment_service import EnvWeatherService


@pytest.fixture
def lifecycle(db_session):
    # 缩小口径便于测试：自动恢复 30 分钟、偶发窗口 300 秒、冷却 5 分钟
    return AlertLifecycleService(
        db_session,
        auto_resolve_minutes=30,
        transient_max_seconds=300,
        cooldown_minutes=5,
    )


@pytest.mark.asyncio
async def test_create_then_dedupe_no_duplicate(db_session, lifecycle):
    # 首次异常 -> 创建告警
    r1 = await lifecycle.register_signal("device", "d-1", True, title="高温")
    assert r1["action"] == "created"
    # 故障未解决期间再次异常 -> 去重归并，不新增
    r2 = await lifecycle.register_signal("device", "d-1", True, title="高温")
    assert r2["action"] == "updated"
    alerts = (await db_session.execute(
        __import__("sqlalchemy").select(Alert)
    )).scalars().all()
    assert len(alerts) == 1
    assert alerts[0].occurrences >= 2


@pytest.mark.asyncio
async def test_auto_resolve_after_30min_normal(db_session, lifecycle):
    await lifecycle.register_signal("device", "d-2", True, title="高温")
    now = datetime.now()
    # 恢复正常 29 分钟 -> 未到 30 分钟，不应解决
    await lifecycle.register_signal("device", "d-2", False, observed_at=now - timedelta(minutes=29))
    open_alerts = (await db_session.execute(
        __import__("sqlalchemy").select(Alert).where(Alert.status.in_(["new", "acknowledged"]))
    )).scalars().all()
    assert len(open_alerts) == 1

    # 恢复正常 31 分钟 -> 自动恢复应解决
    # 先重置 normal_since_at 到 30 分钟前，模拟"连续正常 30 分钟"
    alert = open_alerts[0]
    alert.normal_since_at = now - timedelta(minutes=31)
    await db_session.commit()
    resolved = await lifecycle.sweep_auto_resolve()
    assert alert.id in resolved
    await db_session.refresh(alert)
    assert alert.status == "resolved"
    assert alert.resolved_at is not None
    assert alert.lifecycle_action == "auto_resolve"


@pytest.mark.asyncio
async def test_transient_short_self_heal_recorded_not_notified(db_session, lifecycle):
    # 异常 -> 秒级恢复：偶发，入库记录但不推送（action=transient_created）
    r1 = await lifecycle.register_signal("device", "d-3", True, title="抖动")
    assert r1["action"] == "created"
    now = datetime.now()
    # 10 秒后恢复（远小于 300s 偶发窗口）
    r2 = await lifecycle.register_signal("device", "d-3", False, observed_at=now + timedelta(seconds=10))
    # 因为时间间隔为秒级(<300s)，应判定为偶发
    assert r2["transient"] is True
    assert r2["action"] == "transient_created"
    events = (await db_session.execute(
        __import__("sqlalchemy").select(TransientFailureEvent)
    )).scalars().all()
    assert len(events) == 1
    assert events[0].duration_seconds < 300


@pytest.mark.asyncio
async def test_cooldown_suppresses_immediate_reactivation(db_session, lifecycle):
    # 制造一个已解决告警（最近 resolved），随后立即异常应被冷却抑制
    await lifecycle.register_signal("device", "d-4", True)
    open_alert = (await db_session.execute(
        __import__("sqlalchemy").select(Alert).where(Alert.target_id == "d-4")
    )).scalars().one()
    open_alert.status = "resolved"
    open_alert.resolved_at = datetime.now()
    await db_session.commit()
    r = await lifecycle.register_signal("device", "d-4", True)
    assert r["action"] == "suppressed_cooldown"


@pytest.mark.asyncio
async def test_reactivate_after_resolved_past_cooldown(db_session):
    # 使用短冷却便于测试
    svc = AlertLifecycleService(db_session, auto_resolve_minutes=30,
                                transient_max_seconds=300, cooldown_minutes=5)
    now = datetime.now()
    await svc.register_signal("device", "d-5", True, observed_at=now - timedelta(hours=1))
    open_alert = (await db_session.execute(
        __import__("sqlalchemy").select(Alert).where(Alert.target_id == "d-5")
    )).scalars().one()
    open_alert.status = "resolved"
    open_alert.resolved_at = now - timedelta(minutes=30)  # 已解决 30 分钟 > 冷却 5 分钟
    await db_session.commit()
    r = await svc.register_signal("device", "d-5", True)
    assert r["action"] == "created"


@pytest.mark.asyncio
async def test_correlation_by_weather_and_buckets(db_session):
    env = EnvWeatherService(db_session)
    # 摄入环境快照
    await env.record(temperature=33.0, humidity=70.0, weather="多云", windspeed=7.0,
                     location_name="主机房", recorded_at=datetime.now())
    await env.record(temperature=20.0, humidity=45.0, weather="晴", windspeed=2.0,
                     location_name="主机房", recorded_at=datetime.now() - timedelta(hours=3))
    # 构造两个偶发事件
    t1 = TransientFailureEvent(alert_id=1, target_type="device", target_id="x1",
                               title="抖动", started_at=datetime.now() - timedelta(minutes=5),
                               duration_seconds=30)
    t2 = TransientFailureEvent(alert_id=2, target_type="device", target_id="x2",
                               title="闪断", started_at=datetime.now() - timedelta(hours=2),
                               duration_seconds=120)
    db_session.add_all([t1, t2])
    await db_session.commit()
    await env.attach_nearest_env(t1)
    await env.attach_nearest_env(t2)
    weather = await env.correlation_by_weather(since=datetime.now() - timedelta(days=1))
    buckets = await env.correlation_by_env_bucket(since=datetime.now() - timedelta(days=1))
    assert weather, "应至少有天气统计"
    total = sum(b["count"] for b in weather)
    assert total == 2
    # 温度区间应含 25~32°C 或 >=38°C（33 度）
    temp_keys = [b["bucket"] for b in buckets["temperature"]]
    assert "25~32°C" in temp_keys or ">=38°C" in temp_keys or "15~25°C" in temp_keys


@pytest.mark.asyncio
async def test_correlation_report_shape(db_session):
    env = EnvWeatherService(db_session)
    data = await env.correlation_report(days=1)
    assert "by_hour" in data
    assert len(data["by_hour"]) == 24
    assert "by_weather" in data
    assert "by_env_bucket" in data
    assert "summary" in data

# ===== API 层 E2E（真实 HTTP 栈） =====
from starlette.testclient import TestClient
from app.main import app


def _auth(client) -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"username": "admin", "password": "Pytest-Admin-12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_e2e_alert_lifecycle_api():
    with TestClient(app) as client:
        h = _auth(client)
        # 异常 -> 建警
        r1 = client.post("/api/v1/alert-lifecycle/signal",
                         json={"target_type": "device", "target_id": "api-d-1",
                               "is_abnormal": True, "title": "高温报警"}, headers=h)
        assert r1.status_code == 200, r1.text
        assert r1.json()["action"] == "created"
        # 未解决期间再次异常 -> 去重
        r2 = client.post("/api/v1/alert-lifecycle/signal",
                         json={"target_type": "device", "target_id": "api-d-1",
                               "is_abnormal": True, "title": "高温报警"}, headers=h)
        assert r2.json()["action"] == "updated"
        # 秒级恢复 -> 偶发
        r3 = client.post("/api/v1/alert-lifecycle/signal",
                         json={"target_type": "device", "target_id": "api-d-1",
                               "is_abnormal": False}, headers=h)
        assert r3.json()["transient"] is True
        # 环境数据摄入
        e = client.post("/api/v1/alert-lifecycle/env",
                        json={"temperature": 33.0, "humidity": 70.0, "weather": "多云",
                              "windspeed": 6.0, "location_name": "E2E-机房"}, headers=h)
        assert e.status_code == 201, e.text
        # 偶发事件列表
        t = client.get("/api/v1/alert-lifecycle/transient", headers=h)
        assert t.status_code == 200
        assert len(t.json()) >= 1
        # 关联统计
        c = client.get("/api/v1/alert-lifecycle/correlation?days=7", headers=h)
        assert c.status_code == 200
        body = c.json()
        assert "by_hour" in body and len(body["by_hour"]) == 24
        # HTML 报表
        rep = client.get("/api/v1/alert-lifecycle/correlation/report?days=7", headers=h)
        assert rep.status_code == 200
        assert "Chart(" in rep.text
