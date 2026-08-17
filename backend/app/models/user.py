"""用户模型"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Boolean, DateTime, Integer, ForeignKey, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.timeutil import now_local


# 用户-角色 多对多关联表
user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False, comment="用户名")
    real_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="真实姓名")
    email: Mapped[Optional[str]] = mapped_column(String(128), unique=True, nullable=True, comment="邮箱")
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="手机号")
    department: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="部门")
    position: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="岗位")
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False, comment="密码哈希")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否启用")
    is_super_admin: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否超级管理员")
    login_attempts: Mapped[int] = mapped_column(Integer, default=0, comment="登录失败次数")
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="锁定至")
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, comment="最后登录时间")
    # 登录后是否需要强制修改密码（如默认管理员初始化后）
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    # 令牌原作版本号：修改密码/注销时+1，用于使已发出 JWT 失效
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local, comment="创建时间"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now_local, onupdate=now_local, comment="更新时间"
    )

    roles: Mapped[list["Role"]] = relationship(
        "Role", secondary=user_roles, back_populates="users", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User {self.username}>"
