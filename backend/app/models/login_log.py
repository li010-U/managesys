"""登录日志模型"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.core.timeutil import now_local

class LoginLog(Base):
    __tablename__ = "login_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, comment="登录用户名")
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="登录IP")
    login_status: Mapped[str] = mapped_column(String(16), nullable=False, comment="登录状态：success/fail")
    fail_reason: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="失败原因")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, comment="登录时间")

    def __repr__(self) -> str:
        return f"<LoginLog {self.username} {self.login_status}>"
