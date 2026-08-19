"""告警规则/告警/告警处理模型"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Float, Text, ForeignKey, Boolean, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.core.timeutil import now_local

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, onupdate=now_local, comment="更新时间")

    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="rule", lazy="selectin")

    def __repr__(self) -> str:
        return f"<AlertRule {self.name}>"


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_status_created_at", "status", "created_at"),
    )

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, comment="创建时间")
    # ==== 智能告警增强（告警收敛/升级） ====
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True, comment="收敛去重键(设备+标题)，同类连续告警归并")
    occurrences: Mapped[int] = mapped_column(Integer, default=1, comment="收敛后的累计发生次数")
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="收敛窗口首次发生时间")
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="确认时间")
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="解决时间")
    escalated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="自动升级时间")
    # ==== 告警生命周期（自动恢复 / 去重防抖 / 偶发故障识别） ====
    # 最近一次异常(越阈/故障)发生时间
    last_abnormal_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="最近异常时间")
    # 参数恢复正常的时间（用于累计"连续正常时长"）
    normal_since_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="恢复正常时间")
    # 自动恢复判定用的阈值（连续正常多少分钟后标记已解决）
    auto_resolve_minutes: Mapped[int] = mapped_column(Integer, default=30, comment="连续正常多少分钟后自动解决")
    # 告警实际持续时长（秒），解决时回填
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="持续时长(秒)")
    # 是否偶发(短时自愈)故障：自愈窗口内恢复，只记录不推送
    is_transient: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否偶发(短时自愈)故障")
    # 冷却到期时间：同一设备已解决后再次异常前的防抖冷却
    cooldown_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="去重防抖冷却到期时间")
    # 告警自动恢复/去重产生的处置方式：auto_resolve/normal/transient/cooldown(null=手动)
    lifecycle_action: Mapped[Optional[str]] = mapped_column(String(24), nullable=True, comment="生命周期处置方式")
    escalated_from: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="升级前级别")

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, comment="处理时间")

    alert: Mapped["Alert"] = relationship("Alert", back_populates="actions", lazy="selectin")

    def __repr__(self) -> str:
        return f"<AlertAction {self.alert_id} {self.action_type}>"

