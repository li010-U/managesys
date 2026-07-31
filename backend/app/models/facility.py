"""数据中心/机房/机柜模型"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Boolean, Integer, DateTime, Float, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base


class DataCenter(Base):
    """数据中心"""
    __tablename__ = "data_centers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="数据中心名称")
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, comment="数据中心编码")
    address: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="地址")
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="描述")
    contact_person: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="联系人")
    contact_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="联系电话")
    contact_email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="联系邮箱")
    status: Mapped[str] = mapped_column(String(16), default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    rooms: Mapped[List["Room"]] = relationship("Room", back_populates="data_center", lazy="selectin")

    def __repr__(self) -> str:
        return f"<DataCenter {self.name}>"


class Room(Base):
    """机房"""
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data_center_id: Mapped[int] = mapped_column(Integer, ForeignKey("data_centers.id", ondelete="CASCADE"), nullable=False, comment="所属数据中心ID")
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="机房名称")
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, comment="机房编号")
    floor: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="楼层")
    area: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="面积(平方米)")
    load_rating: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="承重等级(kg/平方米)")
    admin_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="管理员姓名")
    admin_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="管理员电话")
    admin_email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="管理员邮箱")
    tier_level: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="Tier等级: Tier I/Tier II/Tier III/Tier IV")
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="描述")
    status: Mapped[str] = mapped_column(String(16), default="active", comment="状态: active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    data_center: Mapped["DataCenter"] = relationship("DataCenter", back_populates="rooms", lazy="selectin")
    racks: Mapped[List["Rack"]] = relationship("Rack", back_populates="room", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Room {self.name}>"


class Rack(Base):
    """机柜"""
    __tablename__ = "racks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    room_id: Mapped[int] = mapped_column(Integer, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, comment="所属机房ID")
    name: Mapped[str] = mapped_column(String(64), nullable=False, comment="机柜名称")
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="机柜编号")
    row_pos: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="所在行")
    col_pos: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="所在列")
    total_units: Mapped[int] = mapped_column(Integer, default=42, comment="总U位数")
    available_units: Mapped[int] = mapped_column(Integer, default=42, comment="可用U位数")
    rated_power: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="额定功率(kW)")
    description: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="描述")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    room: Mapped["Room"] = relationship("Room", back_populates="racks", lazy="selectin")
    devices: Mapped[List["Device"]] = relationship("Device", back_populates="rack", lazy="selectin")

    def __repr__(self) -> str:
        return f"<Rack {self.code}>"
