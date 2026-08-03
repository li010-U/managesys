"""验证码模型"""
from datetime import datetime
from sqlalchemy import String, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class CaptchaCode(Base):
    """验证码记录表"""
    __tablename__ = "captcha_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    captcha_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False, comment="验证码ID")
    code: Mapped[str] = mapped_column(String(8), nullable=False, comment="验证码答案")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="创建时间")
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="过期时间")
    used: Mapped[bool] = mapped_column(default=False, comment="是否已使用")

    def is_expired(self) -> bool:
        """检查是否已过期"""
        return datetime.now() > self.expires_at

    def is_valid(self, code: str) -> bool:
        """验证验证码是否正确且未过期"""
        if self.is_expired() or self.used:
            return False
        return self.code.lower() == code.lower()
