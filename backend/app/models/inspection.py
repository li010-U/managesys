"""设备巡检相关模型"""
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Float, Text, ForeignKey, Boolean, JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base


class InspectionTemplate(Base):
    """巡检模板"""
    __tablename__ = "inspection_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="模板名称")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="模板描述")
    device_type_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("device_types.id", ondelete="SET NULL"), nullable=True, comment="适用的设备类型")
    items: Mapped[Optional[list]] = mapped_column(JSON, nullable=True, comment="巡检项配置")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<InspectionTemplate {self.name}>"


class InspectionPlan(Base):
    """巡检计划"""
    __tablename__ = "inspection_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="计划名称")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="计划描述")
    
    plan_type: Mapped[str] = mapped_column(String(16), default="periodic", comment="计划类型: periodic/one_time")
    frequency: Mapped[str] = mapped_column(String(16), default="daily", comment="周期: daily/weekly/monthly")
    weekdays: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="执行星期,逗号分隔如: 1,3,5")
    day_of_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="每月几号执行")
    execute_time: Mapped[str] = mapped_column(String(8), default="09:00", comment="执行时间 HH:MM")
    
    facility_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True, comment="关联机房")
    template_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("inspection_templates.id", ondelete="SET NULL"), nullable=True, comment="关联模板")
    
    assignee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="巡检人")
    status: Mapped[str] = mapped_column(String(16), default="active", comment="状态: active/paused/stopped")
    
    next_execute_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="下次执行日期")
    last_execute_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="上次执行日期")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    template: Mapped[Optional["InspectionTemplate"]] = relationship("InspectionTemplate", lazy="selectin")
    facility: Mapped[Optional["Facility"]] = relationship("Facility", lazy="selectin")
    assignee: Mapped[Optional["User"]] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<InspectionPlan {self.name}>"


class InspectionTask(Base):
    """巡检任务"""
    __tablename__ = "inspection_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("inspection_plans.id", ondelete="CASCADE"), nullable=False, comment="关联计划")
    plan_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="计划名称快照")
    
    facility_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True, comment="关联机房")
    
    status: Mapped[str] = mapped_column(String(16), default="pending", comment="状态: pending/in_progress/completed/overdue")
    priority: Mapped[str] = mapped_column(String(16), default="normal", comment="优先级")
    
    assignee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="巡检人")
    
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False, comment="计划执行日期")
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="实际开始时间")
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="实际完成时间")
    
    total_items: Mapped[int] = mapped_column(Integer, default=0, comment="总巡检项")
    completed_items: Mapped[int] = mapped_column(Integer, default=0, comment="已完成项")
    abnormal_items: Mapped[int] = mapped_column(Integer, default=0, comment="异常项")
    
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="备注")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    plan: Mapped["InspectionPlan"] = relationship("InspectionPlan", lazy="selectin")
    facility: Mapped[Optional["Facility"]] = relationship("Facility", lazy="selectin")
    assignee: Mapped[Optional["User"]] = relationship("User", lazy="selectin")
    records: Mapped[List["InspectionRecord"]] = relationship("InspectionRecord", back_populates="task", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<InspectionTask {self.plan_name}>"


class InspectionRecord(Base):
    """巡检记录"""
    __tablename__ = "inspection_records"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("inspection_tasks.id", ondelete="CASCADE"), nullable=False, comment="关联任务")
    device_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, comment="关联设备")
    
    item_name: Mapped[str] = mapped_column(String(128), nullable=False, comment="巡检项名称")
    item_key: Mapped[str] = mapped_column(String(64), nullable=False, comment="巡检项标识")
    check_content: Mapped[str] = mapped_column(String(512), nullable=False, comment="检查内容")
    
    check_result: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="检查结果: normal/abnormal/na")
    check_value: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="检查值")
    check_remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="检查备注")
    
    inspector_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, comment="检查人")
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="检查时间")

    task: Mapped["InspectionTask"] = relationship("InspectionTask", back_populates="records", lazy="selectin")
    device: Mapped[Optional["Device"]] = relationship("Device", lazy="selectin")
    inspector: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<InspectionRecord {self.item_name}>"


class InspectionIssue(Base):
    """巡检问题"""
    __tablename__ = "inspection_issues"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, ForeignKey("inspection_tasks.id", ondelete="CASCADE"), nullable=False, comment="关联任务")
    record_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("inspection_records.id", ondelete="SET NULL"), nullable=True, comment="关联记录")
    device_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, comment="关联设备")
    
    issue_title: Mapped[str] = mapped_column(String(256), nullable=False, comment="问题标题")
    issue_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="问题描述")
    severity: Mapped[str] = mapped_column(String(16), default="normal", comment="严重程度: low/normal/serious/critical")
    
    status: Mapped[str] = mapped_column(String(16), default="open", comment="状态: open/in_progress/resolved/closed")
    
    reporter_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, comment="上报人")
    handler_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="处理人")
    
    resolve_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="处理内容")
    resolve_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="处理时间")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    task: Mapped["InspectionTask"] = relationship("InspectionTask", lazy="selectin")
    record: Mapped[Optional["InspectionRecord"]] = relationship("InspectionRecord", lazy="selectin")
    device: Mapped[Optional["Device"]] = relationship("Device", lazy="selectin")
    reporter: Mapped["User"] = relationship("User", foreign_keys=[reporter_id], lazy="selectin")
    handler: Mapped[Optional["User"]] = relationship("User", foreign_keys=[handler_id], lazy="selectin")

    def __repr__(self) -> str:
        return f"<InspectionIssue {self.issue_title}>"
