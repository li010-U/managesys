"""告警规则/告警/告警处理模型"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Float, Text, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="规则名称")
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, comment="规则编码")
    metric: Mapped[str] = mapped_column(String(64), nullable=False, comment="监控指标：temperature/humidity/cpu/memory/disk")
    condition: Mapped[str] = mapped_column(String(8), nullable=False, comment="条件：gt/lt/eq/gte/lte")
    threshold: Mapped[float] = mapped_column(Float, nullable=False, comment="阈值")
    alert_level: Mapped[str] = mapped_column(String(16), default="general", comment="告警级别：general/serious/emergency")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    notify_methods: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, comment="通知方式：email/sms")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="rule", lazy="selectin")

    def __repr__(self) -> str:
        return f"<AlertRule {self.name}>"


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_rule_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("alert_rules.id", ondelete="SET NULL"), nullable=True, comment="触发规则ID")
    device_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, comment="关联设备ID")
    target_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="告警对象类型：device/sensor/system")
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, comment="告警对象ID")
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="告警标题")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="告警描述")
    level: Mapped[str] = mapped_column(String(16), default="general", comment="告警级别：general/serious/emergency")
    status: Mapped[str] = mapped_column(String(16), default="new", comment="状态：new/acknowledged/resolved/ignored")
    source: Mapped[str] = mapped_column(String(16), default="system", comment="来源：sensor/monitor/system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    rule: Mapped[Optional["AlertRule"]] = relationship("AlertRule", back_populates="alerts", lazy="selectin")
    actions: Mapped[List["AlertAction"]] = relationship("AlertAction", back_populates="alert", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Alert {self.title}>"


class AlertAction(Base):
    __tablename__ = "alert_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False, comment="告警ID")
    action_type: Mapped[str] = mapped_column(String(16), nullable=False, comment="处理类型：acknowledge/resolve/ignore")
    operator: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="处理人")
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="处理备注")
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="根因分析")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="处理时间")

    alert: Mapped["Alert"] = relationship("Alert", back_populates="actions", lazy="selectin")

    def __repr__(self) -> str:
        return f"<AlertAction {self.alert_id} {self.action_type}>"
