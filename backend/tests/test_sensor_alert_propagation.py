# -*- coding: utf-8 -*-
"""传感器采集 -> 告警生命周期 振合复回归测试。

record_data 越阈时应制造异常信号产生告警、恢复正常时应触发自动恢复计时，保持监控与告警中心口径一致。"""
import pytest
from sqlalchemy import select

from app.models.sensor import Sensor
from app.models.alert import Alert
from app.models.facility import DataCenter, Room
from app.services.sensor_service import SensorService


async def _make_room(db):
    dc = DataCenter(name="dc-propagate", code="dc-propagate-1")
    db.add(dc)
    await db.flush()
    room = Room(data_center_id=dc.id, name="room-propagate", code="room-propagate-1")
    db.add(room)
    await db.flush()
    return room


async def _make_sensor(db, room_id):
    sensor = Sensor(
        room_id=room_id,
        name="tempa",
        code="sensor-propagate-1",
        sensor_type="temperature",
        threshold_min=10.0,
        threshold_max=30.0,
        alert_level="serious",
    )
    db.add(sensor)
    await db.flush()
    return sensor


async def _find_open(db, sensor_id):
    res = await db.execute(
        select(Alert).where(
            Alert.target_type == "sensor",
            Alert.target_id == str(sensor_id),
            Alert.status.in_(["new", "acknowledged"]),
        )
    )
    return list(res.scalars().all())


@pytest.mark.asyncio
async def test_sensor_breach_creates_alert_and_recovery(db_session):
    room = await _make_room(db_session)
    sensor = await _make_sensor(db_session, room.id)
    svc = SensorService(db_session)

    # 越阈采集点 -> 应产生告警
    await svc.record_data(sensor.id, 40.0)
    await db_session.flush()
    alerts = await _find_open(db_session, sensor.id)
    assert len(alerts) == 1
    assert alerts[0].source == "monitor"
    assert alerts[0].target_type == "sensor"

    # 再次越阈 -> 去重合并，不新增告警
    await svc.record_data(sensor.id, 45.0)
    await db_session.flush()
    assert len(await _find_open(db_session, sensor.id)) == 1

    # 恢复正常 -> 触发自动恢复计时（设置 normal_since_at）
    await svc.record_data(sensor.id, 20.0)
    await db_session.flush()
    alert = (await db_session.execute(
        select(Alert).where(
            Alert.target_type == "sensor",
            Alert.target_id == str(sensor.id),
        )
    )).scalars().one()
    assert alert.status == "new"
    assert alert.normal_since_at is not None
