"""设备类型模型"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base


class DeviceType(Base):
    __tablename__ = "device_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="类型名称")
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, comment="类型编码")
    category: Mapped[str] = mapped_column(String(32), nullable=False, comment="设备分类: server/network/storage/security/power")
    manufacturer: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="厂商")
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="型号")
    spec_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="规格描述")
    thresholds: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="传感器阈值配置")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    devices: Mapped[List["Device"]] = relationship("Device", back_populates="device_type", lazy="selectin")

    def __repr__(self) -> str:
        return f"<DeviceType {self.name}>"
