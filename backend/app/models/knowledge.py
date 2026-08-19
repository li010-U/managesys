"""知识库文章模型"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.core.timeutil import now_local


class KnowledgeArticle(Base):
    """知识库文章"""
    __tablename__ = "kb_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="标题")
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="分类")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="内容")
    source_order_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="来源工单ID")
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now_local)

    creator: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<KnowledgeArticle {self.title}>"
