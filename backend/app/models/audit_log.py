"""审计日志模型"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.core.timeutil import now_local


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="操作用户ID")
    username: Mapped[str] = mapped_column(String(64), nullable=False, comment="操作用户名")
    action: Mapped[str] = mapped_column(String(64), nullable=False, comment="操作类型：login/logout/create/update/delete/export/mount/unmount/move")
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="操作对象类型：user/role/device/room/rack/system/alert/...")
    target_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="操作对象ID")
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="操作详情")
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="操作IP")
    request_path: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="请求路径")
    user_agent: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="用户代理")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, comment="创建时间")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.target_type}>"
