"""IP 地址台账与子网管理模型"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.core.timeutil import now_local


class IpSubnet(Base):
    """托管子网定义：网段/掩码/网关/VLAN 等规划信息。"""
    __tablename__ = "ip_subnets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="子网名称")
    network: Mapped[str] = mapped_column(String(64), nullable=False, comment="网段地址(如 10.0.0.0)")
    prefix: Mapped[int] = mapped_column(Integer, nullable=False, default=24, comment="前缀长度")
    gateway: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="网关")
    vlan: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="VLAN")
    vlan_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("vlans.id", ondelete="SET NULL"), nullable=True, index=True, comment="\u5173\u8054 VLAN")
    description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="用途说明")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", comment="active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, comment="创建时间")

    addresses: Mapped[list["IpAddress"]] = relationship("IpAddress", back_populates="subnet", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<IpSubnet {self.network}/{self.prefix}>"


class IpAddress(Base):
    """IP 台账条目：记录单个 IP 的分配/预留/空闲状态及归属。"""
    __tablename__ = "ip_addresses"
    # 采用全局唯一约束：一个 IP 地址仅允许一行，绝不允许重复分配
    # （旧的 (subnet_id, address) 组合约束在 subnet_id 为 NULL 时不生效，导致可写入重复 IP）
    __table_args__ = (UniqueConstraint("address", name="uq_ip_address_addr"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    subnet_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("ip_subnets.id", ondelete="CASCADE"), nullable=True, comment="所属子网")
    address: Mapped[str] = mapped_column(String(64), nullable=False, comment="IP 地址")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="free", comment="free/reserved/allocated")
    device_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, comment="占用设备")
    used_as: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="management/business/oob")
    remark: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, onupdate=now_local, comment="更新时间")

    subnet: Mapped[Optional["IpSubnet"]] = relationship("IpSubnet", back_populates="addresses")
    device: Mapped[Optional["Device"]] = relationship("Device")
    def __repr__(self) -> str:
        return f"<IpAddress {self.address} {self.status}>"


class IpAddressHistory(Base):
    """IP 变更历史：记录单条 IP 的状态/归属/用途变化，支持回放与审计。"""
    __tablename__ = "ip_address_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ip_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True, comment="关联IP台账ID")
    address: Mapped[str] = mapped_column(String(64), nullable=False, index=True, comment="IP 地址")
    field_changed: Mapped[str] = mapped_column(String(32), nullable=False, comment="变更字段: status/device/used_as/remark")
    from_value: Mapped[Optional[Text]] = mapped_column(Text, nullable=True, comment="变更前值")
    to_value: Mapped[Optional[Text]] = mapped_column(Text, nullable=True, comment="变更后值")
    operator: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="操作人")
    source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="来源: manual/allocate/device_sync/conflict_resolve/release")
    remark: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, index=True, comment="发生时间")

    def __repr__(self) -> str:
        return f"<IpAddressHistory {self.address} {self.field_changed}>"
