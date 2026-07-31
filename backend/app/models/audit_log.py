"""审计日志模型"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.db.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="操作用户ID")
    username: Mapped[str] = mapped_column(String(64), nullable=False, comment="操作用户名")
    action: Mapped[str] = mapped_column(String(64), nullable=False, comment="操作类型：login/logout/create/update/delete/export")
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, comment="操作对象类型：user/role/device/room/rack/system")
    target_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="操作对象ID")
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="操作详情")
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="操作IP")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} {self.target_type}>"
