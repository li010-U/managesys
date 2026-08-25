# -*- coding: utf-8 -*-
"""数据保留与传感器异常留痕的回归测试。"""
from datetime import datetime, timedelta

import pytest

from app.models.sensor import Sensor, SensorData, SensorAnomalyGap
from app.models.alert import Alert
from app.models.facility import DataCenter, Room
from app.schemas.sensor import SensorDataResponse
from app.services.sensor_service import SensorService, MAX_TREND_POINTS
from app.services.sensor_anomaly_service import SensorAnomalyService


async def _make_room(db):
    dc = DataCenter(name="dc1", code="dc-code-1")
    db.add(dc)
    await db.flush()
    room = Room(data_center_id=dc.id, name="room1", code="room-code-1")
    db.add(room)
    await db.flush()
    return room


def _mk_sensor(room_id, **kw):
    base = dict(
        room_id=room_id,
        name="t1",
        code="sensor-t1",
        sensor_type="temperature",
        threshold_min=10.0,
        threshold_max=30.0,
    )
    base.update(kw)
    return Sensor(**base)


def _mk_gap(sensor_id, alert_id, detected_at, ws=None, we=None):
    return SensorAnomalyGap(
        sensor_id=sensor_id, alert_id=alert_id, detected_at=detected_at,
        window_start=ws, window_end=we,
    )


def _mk_alert(sensor_id, created_at, source="monitor", level="warning"):
    return Alert(
        alert_rule_id=None,
        device_id=None,
        target_type="sensor",
        target_id=str(sensor_id),
        title="越阈测试",
        description="between points",
        level=level,
        status="new",
        source=source,
        created_at=created_at,
    )


@pytest.fixture
async def sensor_with_data(db_session):
    room = await _make_room(db_session)
    sensor = Sensor(
        room_id=room.id, name="t1", code="s1", sensor_type="temperature",
        threshold_min=10.0, threshold_max=30.0,
    )
    db_session.add(sensor)
    await db_session.flush()
    return sensor


@pytest.mark.asyncio
async def test_record_data_marks_normal(db_session, sensor_with_data):
    svc = SensorService(db_session)
    sd = await svc.record_data(sensor_with_data.id, 22.5)
    assert sd.source_mark == "normal"


@pytest.mark.asyncio
async def test_record_data_marks_abnormal_when_breaching(db_session, sensor_with_data):
    svc = SensorService(db_session)
    sd = await svc.record_data(sensor_with_data.id, 45.0)  # > max 30
    assert sd.source_mark == "abnormal"
    sd2 = await svc.record_data(sensor_with_data.id, 5.0)  # < min 10
    assert sd2.source_mark == "abnormal"


@pytest.mark.asyncio
async def test_run_retention_deletes_expired_only(db_session):
    now = datetime.now()
    svc = SensorAnomalyService(db_session)

    room = await _make_room(db_session)
    sensor = Sensor(room_id=room.id, name="r", code="r1", sensor_type="temperature")
    db_session.add(sensor)
    await db_session.flush()

    old = SensorData(sensor_id=sensor.id, value=1.0, recorded_at=now - timedelta(days=365))
    fresh = SensorData(sensor_id=sensor.id, value=1.0, recorded_at=now - timedelta(days=10))
    db_session.add_all([old, fresh])
    await db_session.flush()

    avg_old = SensorAnomalyGap(sensor_id=sensor.id, alert_id=1, detected_at=now - timedelta(days=365))
    agg_fresh = SensorAnomalyGap(sensor_id=sensor.id, alert_id=2, detected_at=now - timedelta(days=10))
    db_session.add_all([avg_old, agg_fresh])
    await db_session.commit()

    res = await svc.run_retention(days=180)
    assert res["sensor_data_deleted"] == 1
    assert res["anomaly_gap_deleted"] == 1

    remaining = (await db_session.execute(
        __import__("sqlalchemy").select(SensorData).where(SensorData.sensor_id == sensor.id)
    )).scalars().all()
    assert len(remaining) == 1 and remaining[0].recorded_at > now - timedelta(days=30)


@pytest.mark.asyncio
async def test_reconcile_detects_between_points_breach(db_session, sensor_with_data):
    now = datetime.now()
    # 传感器默认阈值 10~30；两个正常采集点（前点 20）
    db_session.add(SensorData(sensor_id=sensor_with_data.id, value=20.0,
                              recorded_at=now - timedelta(hours=3), source_mark="normal"))
    await db_session.commit()

    # 预警时刻落在两采集点之间（距上一采集点 > 期望间隔容差），采集点本身正常
    alert = _mk_alert(sensor_with_data.id, now - timedelta(hours=1))
    db_session.add(alert)
    await db_session.commit()

    svc = SensorAnomalyService(db_session)
    added = await svc.reconcile_from_alerts(since=now - timedelta(days=1))
    assert added >= 1

    # 幂等：再次运行不重复
    added2 = await svc.reconcile_from_alerts(since=now - timedelta(days=1))
    assert added2 == 0


@pytest.mark.asyncio
async def test_get_recent_data_downsample_validates_as_sensor_data_response(db_session, sensor_with_data):
    """校验近 hours 数据若能降采样为 _PointSample 并映射为 SensorDataResponse。
    若 route 的 model_validate 招 ValidationError -> 500，回归将被拘获（此测试可发现该回归）。
    同时验证降采样结果的时间跨度满足近 N 小时的要求。"""
    now = datetime.now()
    total = 2000  # 超过 limit(1000) 与 MAX_TREND_POINTS(240)，触发并验证降采样
    step_seconds = (24 * 3600) / total
    for i in range(total):
        db_session.add(SensorData(
            sensor_id=sensor_with_data.id,
            value=float(i),
            recorded_at=now - timedelta(hours=24) + timedelta(seconds=i * step_seconds),
        ))
    await db_session.commit()

    svc = SensorService(db_session)
    data = await svc.get_recent_data(sensor_with_data.id, limit=1000, hours=24)

    assert len(data) > 0
    assert len(data) <= MAX_TREND_POINTS
    validated = [SensorDataResponse.model_validate(d) for d in data]
    assert len(validated) == len(data)
    assert all(v.sensor_id == sensor_with_data.id for v in validated)

    earliest = min(validated, key=lambda v: v.recorded_at).recorded_at
    latest = max(validated, key=lambda v: v.recorded_at).recorded_at
    assert (now - earliest).total_seconds() <= 25 * 3600, f"earliest 超出范围: {earliest}"
    assert (latest - now).total_seconds() < 3600, f"latest 超出范围: {latest}"
    span_hours = (latest - earliest).total_seconds() / 3600
    assert span_hours >= 20, f"降采样后跨度不足: {span_hours:.1f}h"


# get_all 需保证单次 SQL，避免 N+1 回归
from sqlalchemy import event as _sa_event

_QUERY_COUNT = {"n": 0}


def _count_sql(conn, cursor, statement, parameters, context, executemany):
    _QUERY_COUNT["n"] += 1


@pytest.mark.asyncio
async def test_get_all_is_single_query_no_nplus1(db_session):
    """校验 /sensors/all 即 get_all 只发 1 条 SQL。
    采用 data_records/anomaly_gaps 用 selectin 加载并与 Sensor 做 eager 关联。
    此前 /sensors/all 需 ~7.4s，采用 lazy='noload' 后降至 0.085s。
    通过校验确保 eager 不退化回 N+1。"""
    room = await _make_room(db_session)
    for i in range(20):
        db_session.add(Sensor(room_id=room.id, name=f"s{i}", code=f"code-{i}",
                              sensor_type="temperature", threshold_min=10.0, threshold_max=30.0))
    await db_session.flush()

    _QUERY_COUNT["n"] = 0
    _sa_event.listen(db_session.get_bind(), "before_cursor_execute", _count_sql, named=True)
    try:
        svc = SensorService(db_session)
        result = await svc.get_all(room_id=room.id)
        assert len(result) == 20
    finally:
        _sa_event.remove(db_session.get_bind(), "before_cursor_execute", _count_sql)

    assert _QUERY_COUNT["n"] == 1, f"get_all 应只发 1 条 SQL，实际 {_QUERY_COUNT['n']} 条，疑似 N+1 回归"


@pytest.mark.asyncio
async def test_run_retention_batches_in_chunks(db_session):
    """分批删除：超过单批上限的过期数据被全部删除，每批不超 batch，且保留新鲜数据。"""
    from datetime import datetime as _dt
    now = _dt.now()
    svc = SensorAnomalyService(db_session)

    room = await _make_room(db_session)
    sensor = Sensor(room_id=room.id, name="r", code="rbatch", sensor_type="temperature")
    db_session.add(sensor)
    await db_session.flush()

    cutoff = now - timedelta(days=180)
    batch = 10
    old_count = 25
    for i in range(old_count):
        db_session.add(SensorData(
            sensor_id=sensor.id, value=1.0,
            recorded_at=now - timedelta(days=365) + timedelta(seconds=i),
        ))
    for i in range(2):
        db_session.add(SensorData(
            sensor_id=sensor.id, value=1.0,
            recorded_at=now - timedelta(days=10) + timedelta(seconds=i),
        ))
    await db_session.commit()

    deleted = await svc._delete_expired_batches(
        SensorData, SensorData.id, SensorData.recorded_at < cutoff, batch
    )
    assert deleted == old_count

    remaining = (await db_session.execute(
        __import__("sqlalchemy").select(SensorData).where(SensorData.sensor_id == sensor.id)
    )).scalars().all()
    assert len(remaining) == 2
    assert all(r.recorded_at > now - timedelta(days=30) for r in remaining)


@pytest.mark.asyncio
async def test_run_retention_layered_normal_vs_abnormal(db_session):
    """分层留存：正常点按 DATA_RETENTION_NORMAL_DAYS(30) 短留，异常点按 180 天长留。

    同一写入时间（60 天前）：
      - source_mark="normal"   -> 被删除（60d > 30d）
      - source_mark="abnormal" -> 被保留（60d < 180d）
    """
    now = datetime.now()
    svc = SensorAnomalyService(db_session)

    room = await _make_room(db_session)
    sensor = Sensor(room_id=room.id, name="r", code="rlayered", sensor_type="temperature")
    db_session.add(sensor)
    await db_session.flush()

    age60 = now - timedelta(days=60)
    db_session.add_all([
        SensorData(sensor_id=sensor.id, value=1.0, recorded_at=age60, source_mark="normal"),
        SensorData(sensor_id=sensor.id, value=1.0, recorded_at=age60, source_mark="abnormal"),
        SensorData(sensor_id=sensor.id, value=1.0, recorded_at=now - timedelta(days=5), source_mark="normal"),
    ])
    await db_session.commit()

    res = await svc.run_retention(days=180)
    assert res["sensor_data_normal_deleted"] == 1
    assert res["sensor_data_abnormal_deleted"] == 0
    assert res["sensor_data_deleted"] == 1

    remaining = list((await db_session.execute(
        __import__("sqlalchemy").select(SensorData).where(SensorData.sensor_id == sensor.id)
    )).scalars())
    assert len(remaining) == 2
    marks = {r.source_mark for r in remaining}
    assert marks == {"normal", "abnormal"}, f"保留集合应为 normal+abnormal, got {marks}"
    retained_abnormal = [r for r in remaining if r.source_mark == "abnormal"][0]
    assert retained_abnormal.recorded_at == age60


@pytest.mark.asyncio
async def test_run_retention_normal_short_cutoff_respected(db_session):
    """验证正常点确实使用 DATA_RETENTION_NORMAL_DAYS，而非统一天数。"""
    now = datetime.now()
    from app.core.config import settings as _settings
    _orig = _settings.DATA_RETENTION_NORMAL_DAYS
    _settings.DATA_RETENTION_NORMAL_DAYS = 10
    try:
        svc = SensorAnomalyService(db_session)
        room = await _make_room(db_session)
        sensor = Sensor(room_id=room.id, name="r", code="rcutoff", sensor_type="temperature")
        db_session.add(sensor)
        await db_session.flush()

        db_session.add_all([
            SensorData(sensor_id=sensor.id, value=1.0, recorded_at=now - timedelta(days=15), source_mark="normal"),
            SensorData(sensor_id=sensor.id, value=1.0, recorded_at=now - timedelta(days=15), source_mark="abnormal"),
        ])
        await db_session.commit()

        res = await svc.run_retention(days=180)
        # 15 天 > 正常 10 天(+3 缓冲=13) -> normal 删；15 天 < 异常 180 天 -> abnormal 留
        assert res["sensor_data_deleted"] == 1
        remaining = list((await db_session.execute(
            __import__("sqlalchemy").select(SensorData).where(SensorData.sensor_id == sensor.id)
        )).scalars())
        assert len(remaining) == 1
        assert remaining[0].source_mark == "abnormal"
    finally:
        _settings.DATA_RETENTION_NORMAL_DAYS = _orig
