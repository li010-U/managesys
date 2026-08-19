# -*- coding: utf-8 -*-
"""环境数据自动轮询采集（EnvPoller）回归测试。"""
import pytest

from sqlalchemy import select
from app.models.env_weather import EnvWeatherRecord
from app.services.environment_service import EnvPoller


@pytest.mark.asyncio
async def test_env_poller_writes_sim_record(db_session):
    values = await EnvPoller(db_session).poll_once(source="sim")
    assert values is not None
    assert "temperature" in values and "weather" in values
    rows = (await db_session.execute(select(EnvWeatherRecord))).scalars().all()
    assert len(rows) == 1
    assert rows[0].weather == values["weather"]
    assert rows[0].temperature == values["temperature"]


@pytest.mark.asyncio
async def test_env_poller_multiple_records(db_session):
    poller = EnvPoller(db_session)
    await poller.poll_once(source="sim")
    await poller.poll_once(source="sim")
    rows = (await db_session.execute(select(EnvWeatherRecord))).scalars().all()
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_env_trend_returns_ascending_series(db_session):
    from datetime import datetime, timedelta
    poller = EnvPoller(db_session)
    # 写入两条时间不同（用 recorded_at 精确注入，避免同秒）
    await poller.service.record(temperature=20.0, humidity=50.0, weather="晴",
                                windspeed=3.0, location_name="机房",
                                recorded_at=datetime.now() - timedelta(hours=2))
    await poller.service.record(temperature=25.0, humidity=60.0, weather="多云",
                                windspeed=5.0, location_name="机房",
                                recorded_at=datetime.now() - timedelta(hours=1))
    trend = await poller.service.env_trend(hours=24, limit=100)
    assert len(trend) == 2
    # 时间升序：第一条早于第二条
    assert trend[0]["recorded_at"] <= trend[1]["recorded_at"]
    assert trend[0]["temperature"] == 20.0
    assert trend[1]["temperature"] == 25.0
    assert "humidity" in trend[0] and "windspeed" in trend[0]

