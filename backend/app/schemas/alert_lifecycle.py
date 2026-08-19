# -*- coding: utf-8 -*-
"""告警生命周期与环境关联统计 Schema"""
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional


class EnvWeatherRecordCreate(BaseModel):
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    weather: Optional[str] = None
    windspeed: Optional[float] = None
    location_id: Optional[int] = None
    location_name: Optional[str] = None
    recorded_at: Optional[datetime] = None


class EnvWeatherRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    location_id: Optional[int]
    location_name: Optional[str]
    temperature: Optional[float]
    humidity: Optional[float]
    weather: Optional[str]
    windspeed: Optional[float]
    recorded_at: datetime


class AlertSignalRequest(BaseModel):
    target_type: str = Field(..., description="对象类型：device/sensor")
    target_id: str = Field(..., description="对象ID（设备/传感器）")
    is_abnormal: bool = Field(..., description="是否异常：True=越阈/故障, False=恢复正常")
    title: Optional[str] = None
    level: str = "general"
    device_id: Optional[int] = None
    metric: Optional[str] = None
    source: str = "monitor"
    observed_at: Optional[datetime] = None


class TransientEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    alert_id: Optional[int]
    target_type: str
    target_id: str
    metric: Optional[str]
    title: str
    started_at: datetime
    recovered_at: Optional[datetime]
    duration_seconds: int
    env_temperature: Optional[float]
    env_humidity: Optional[float]
    env_weather: Optional[str]
    env_windspeed: Optional[float]
    location_id: Optional[int]
    location_name: Optional[str]
