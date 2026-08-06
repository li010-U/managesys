"""?????"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base


class KnowledgeArticle(Base):
    """?????"""
    __tablename__ = "kb_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="??")
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="??")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="??")
    source_order_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="????ID")
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    creator: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<KnowledgeArticle {self.title}>"
