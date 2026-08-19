"""VLAN \u5b9e\u4f53\uff1a\u7528\u4e8e\u7ec8\u7aef\u7f51\u6bb5\u7684 VLAN \u5206\u7c7b\u4e0e\u6309\u673a\u623f\u7edf\u8ba1\u3002"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.core.timeutil import now_local


class Vlan(Base):
    __tablename__ = "vlans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    vlan_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True, comment="VLAN 编号")
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="", comment="VLAN 名称")
    description: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, comment="\u7528\u9014\u8bf4\u660e")
    room_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("rooms.id", ondelete="SET NULL"), nullable=True, index=True, comment="\u5173\u8054\u673a\u623f")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", comment="active/disabled")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local, comment="\u521b\u5efa\u65f6\u95f4")

    def __repr__(self) -> str:
        return f"<Vlan {self.vlan_id} {self.name}>"
