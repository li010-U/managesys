"""传感器与传感器数据模型"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Float, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Sensor(Base):
    __tablename__ = "sensors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, comment="所属机房")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="传感器名称")
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, comment="传感器编号")
    sensor_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="类型：temperature/humidity/smoke/water/door_magnetic")
    install_position: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="安装位置")
    status: Mapped[str] = mapped_column(String(16), default="offline", comment="状态：online/offline")
    current_value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="当前数值")
    last_update_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后更新时间")
    threshold_min: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="阈值下限")
    threshold_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="阈值上限")
    alert_level: Mapped[str] = mapped_column(String(16), default="general", comment="告警级别：general/serious/emergency")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    data_records: Mapped[List["SensorData"]] = relationship("SensorData", back_populates="sensor", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Sensor {self.name}>"


class SensorData(Base):
    __tablename__ = "sensor_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sensor_id: Mapped[int] = mapped_column(Integer, ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False, comment="传感器ID")
    value: Mapped[float] = mapped_column(Float, nullable=False, comment="数值")
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="记录时间")

    sensor: Mapped["Sensor"] = relationship("Sensor", back_populates="data_records", lazy="selectin")

    def __repr__(self) -> str:
        return f"<SensorData {self.sensor_id} {self.value}>"
