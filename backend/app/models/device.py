"""设备与生命周期模型"""
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Float, Text, ForeignKey, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("device_types.id", ondelete="RESTRICT"), nullable=False, comment="设备类型")
    rack_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("racks.id", ondelete="SET NULL"), nullable=True, comment="所在机柜")

    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="设备名称")
    asset_number: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True, comment="资产编号")
    serial_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="序列号")
    brand: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="品牌")
    model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="型号")

    cpu_info: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="CPU信息")
    memory_info: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="内存信息")
    disk_info: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="硬盘信息")
    network_info: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="网卡信息")

    purchase_order: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="采购单号")
    purchase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="购买日期")
    vendor: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="供应商")
    purchase_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="采购金额")
    warranty_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="维保开始日期")
    warranty_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="维保结束日期")
    warranty_vendor: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="维保商")

    start_u: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="起始U位")
    end_u: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="结束U位")
    management_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="管理IP")
    business_ip: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="业务IP")
    mac_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="MAC地址")
    out_of_band_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="带外地址")

    status: Mapped[str] = mapped_column(String(16), default="in_stock", comment="状态：in_stock/mounted/running/offline/scrapped")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    device_type: Mapped["DeviceType"] = relationship("DeviceType", back_populates="devices", lazy="selectin")
    rack: Mapped[Optional["Rack"]] = relationship("Rack", back_populates="devices", lazy="selectin")
    lifecycles: Mapped[List["DeviceLifecycle"]] = relationship("DeviceLifecycle", back_populates="device", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Device {self.asset_number}>"


class DeviceLifecycle(Base):
    __tablename__ = "device_lifecycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, comment="设备ID")
    action: Mapped[str] = mapped_column(String(32), nullable=False, comment="操作：mount/unmount/scrap/change")
    from_status: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="变更前状态")
    to_status: Mapped[str] = mapped_column(String(16), nullable=False, comment="变更后状态")
    operator: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="操作人")
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    device: Mapped["Device"] = relationship("Device", back_populates="lifecycles", lazy="selectin")

    def __repr__(self) -> str:
        return f"<DeviceLifecycle {self.device_id} {self.action}>"
