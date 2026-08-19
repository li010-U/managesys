# -*- coding: utf-8 -*-
"""环境/气象数据 与 偶发故障事件模型。

- EnvWeatherRecord：按时间+位置记录的温度/湿度/天气/风速等环境气象数据，
  供偶发故障与环境的关联统计使用。
- TransientFailureEvent：短时自愈的偶发故障事件留痕（出现-恢复区间+环境快照），
  只记录、不推送，用于偶发故障-环境关联统计与仪表化分析。
"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Float, Text, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.core.timeutil import now_local


class EnvWeatherRecord(Base):
    __tablename__ = "env_weather_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 位置维度：可关联机房/数据中心；未关联时可为空或字符串位置名
    location_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="关联位置ID(机房/数据中心)")
    location_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="位置名称")
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="温度(°C)")
    humidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="湿度(%RH)")
    weather: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="天气类型：晴/多云/阴/雨/雪/风等")
    windspeed: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="风速(m/s)")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, index=True, comment="记录时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, comment="创建时间")

    def __repr__(self) -> str:
        return f"<EnvWeatherRecord {self.recorded_at} {self.weather}>"


class TransientFailureEvent(Base):
    """短时自愈的偶发故障事件留痕（只记录、不推送）。

    与 alerts 互补：真正进入本表的偶发事件在告警上已标记 is_transient，
    这里额外保存发生-恢复区间与关联的环境/气象快照，用于关联统计。
    """

    __tablename__ = "transient_failure_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="关联告警ID")
    target_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="对象类型：device/sensor")
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="对象ID")
    metric: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="指标")
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="故障标题")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="故障开始时间")
    recovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="自愈恢复时间")
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, comment="持续时长(秒)")
    # 环境/气象快照（发生时点最接近的一条 env_weather_records）
    env_temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="发生时温度(°C)")
    env_humidity: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="发生时湿度(%RH)")
    env_weather: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="发生时天气")
    env_windspeed: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="发生时风速(m/s)")
    location_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="位置ID")
    location_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="位置名称")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, comment="创建时间")

    def __repr__(self) -> str:
        return f"<TransientFailureEvent {self.target_id} {self.duration_seconds}s>"
