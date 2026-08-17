"""工单相关模型"""
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Date, Float, Text, ForeignKey, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.core.timeutil import now_local


class WorkOrderCategory(Base):
    """工单分类"""
    __tablename__ = "work_order_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, comment="分类名称")
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True, comment="分类编码")
    icon: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="图标")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local)
    need_approval: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否需要审批")


    def __repr__(self) -> str:
        return f"<WorkOrderCategory {self.name}>"


class WorkOrder(Base):
    """工单"""
    __tablename__ = "work_orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True, comment="工单编号")
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="工单标题")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="工单描述")
    
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("work_order_categories.id", ondelete="SET NULL"), nullable=True, comment="工单分类")
    priority: Mapped[str] = mapped_column(String(16), default="normal", comment="优先级: low/normal/high/urgent")
    
    # 关联信息
    device_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, comment="关联设备")
    facility_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, comment="关联机房")
    
    # 流程信息
    status: Mapped[str] = mapped_column(String(16), default="pending", comment="状态: pending/assigned/processing/pending_verify/completed/closed")
    creator_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, comment="创建人")
    assignee_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="处理人")
    
    # 计划与实际
    plan_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, comment="计划完成日期")
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="实际开始时间")
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="实际完成时间")
    
    # 评估
    estimated_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="预估工时(小时)")
    actual_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="实际工时(小时)")
    
    # 结果
    result: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="处理结果")
    satisfaction: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="满意度评分 1-5")
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="用户反馈")
    alert_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("alerts.id", ondelete="SET NULL"), nullable=True, comment="关联告警ID")
    approved_by: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="审批人")
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="审批时间")
    reject_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="拒绝原因")
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, onupdate=now_local, comment="更新时间")
    
    category: Mapped[Optional["WorkOrderCategory"]] = relationship("WorkOrderCategory", lazy="selectin")
    device: Mapped[Optional["Device"]] = relationship("Device", lazy="selectin")
    facility: Mapped[Optional["Room"]] = relationship("Room", lazy="selectin")
    creator: Mapped["User"] = relationship("User", foreign_keys=[creator_id], lazy="selectin")
    assignee: Mapped[Optional["User"]] = relationship("User", foreign_keys=[assignee_id], lazy="selectin")
    comments: Mapped[List["WorkOrderComment"]] = relationship("WorkOrderComment", back_populates="work_order", lazy="selectin", cascade="all, delete-orphan")
    attachments: Mapped[List["WorkOrderAttachment"]] = relationship("WorkOrderAttachment", back_populates="work_order", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<WorkOrder {self.order_no}>"


class WorkOrderComment(Base):
    """工单评论/处理记录"""
    __tablename__ = "work_order_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, comment="工单ID")
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, comment="评论人")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="评论内容")
    comment_type: Mapped[str] = mapped_column(String(16), default="normal", comment="类型: normal/process/verify/close")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local)

    work_order: Mapped["WorkOrder"] = relationship("WorkOrder", back_populates="comments", lazy="selectin")
    user: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<WorkOrderComment {self.work_order_id}>"


class WorkOrderAttachment(Base):
    """工单附件"""
    __tablename__ = "work_order_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_order_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False)
    file_name: Mapped[str] = mapped_column(String(256), nullable=False, comment="文件名")
    file_path: Mapped[str] = mapped_column(String(512), nullable=False, comment="文件路径")
    file_size: Mapped[int] = mapped_column(Integer, nullable=True, comment="文件大小(字节)")
    file_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="文件类型")
    uploader_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local)

    work_order: Mapped["WorkOrder"] = relationship("WorkOrder", back_populates="attachments", lazy="selectin")
    uploader: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<WorkOrderAttachment {self.file_name}>"


class WorkOrderAutoRule(Base):
    """???????"""
    __tablename__ = "work_order_auto_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="规则名称")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    match_keyword: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="匹配关键字(关键词/标签)")
    match_category_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="匹配分类ID")
    match_priority: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="匹配优先级")
    action_set_priority: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, comment="动作:设置优先级")
    action_assign_user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="动作:指派用户")
    action_auto_complete: Mapped[bool] = mapped_column(Boolean, default=False, comment="动作:自动完成(满足规则自动)")
    sort: Mapped[int] = mapped_column(Integer, default=0, comment="排序(数值越小越前)")
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local)

    def __repr__(self) -> str:
        return f"<WorkOrderAutoRule {self.name}>"
