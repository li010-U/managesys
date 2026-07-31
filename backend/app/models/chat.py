"""AI对话模型"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class ChatConversation(Base):
    __tablename__ = "chat_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, comment="用户ID")
    title: Mapped[str] = mapped_column(String(256), default="新对话", comment="对话标题")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    messages: Mapped[List["ChatMessage"]] = relationship("ChatMessage", back_populates="conversation", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChatConversation {self.title}>"


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False, comment="对话ID")
    role: Mapped[str] = mapped_column(String(16), nullable=False, comment="角色：user/assistant/system")
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True, comment="扩展元数据（模型、token数等）")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    conversation: Mapped["ChatConversation"] = relationship("ChatConversation", back_populates="messages", lazy="selectin")

    def __repr__(self) -> str:
        return f"<ChatMessage {self.conversation_id} {self.role}>"
