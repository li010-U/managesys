# -*- coding: utf-8 -*-
"""数据保留与传感器异常留痕的回归测试。"""
from datetime import datetime, timedelta

import pytest

from app.models.sensor import Sensor, SensorData, SensorAnomalyGap
from app.models.alert import Alert
from app.models.facility import DataCenter, Room
from app.services.sensor_service import SensorService
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
