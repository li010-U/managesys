"""业务系统/部署关联/系统文档模型"""
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey, JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from app.db.base import Base

class BusinessSystem(Base):
    __tablename__ = "business_systems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, comment="系统名称")
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, comment="系统编码")
    category: Mapped[str] = mapped_column(String(32), default="other", comment="分类：OA/ERP/CRM/DB/Middleware/Other")
    access_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, comment="访问URL")
    admin_name: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="管理员")
    admin_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, comment="管理员电话")
    admin_email: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="管理员邮箱")
    remark: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="备注")
    status: Mapped[str] = mapped_column(String(16), default="active", comment="状态：active/maintenance/offline")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间")

    deployments: Mapped[List["DeploymentRelation"]] = relationship("DeploymentRelation", back_populates="system", lazy="selectin", cascade="all, delete-orphan")
    documents: Mapped[List["SystemDocument"]] = relationship("SystemDocument", back_populates="system", lazy="selectin", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<BusinessSystem {self.name}>"


class DeploymentRelation(Base):
    __tablename__ = "deployment_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    system_id: Mapped[int] = mapped_column(Integer, ForeignKey("business_systems.id", ondelete="CASCADE"), nullable=False, comment="业务系统ID")
    device_id: Mapped[int] = mapped_column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, comment="设备ID")
    service_port: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="服务端口")
    process_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, comment="进程名")
    system_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="系统版本")
    middleware_version: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="中间件版本")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    system: Mapped["BusinessSystem"] = relationship("BusinessSystem", back_populates="deployments", lazy="selectin")
    device: Mapped["Device"] = relationship("Device", lazy="selectin")

    def __repr__(self) -> str:
        return f"<DeploymentRelation {self.system_id}-{self.device_id}>"


class SystemDocument(Base):
    __tablename__ = "system_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    system_id: Mapped[int] = mapped_column(Integer, ForeignKey("business_systems.id", ondelete="CASCADE"), nullable=False, comment="业务系统ID")
    doc_type: Mapped[str] = mapped_column(String(32), nullable=False, comment="文档类型：architecture/operation/manual/change")
    title: Mapped[str] = mapped_column(String(256), nullable=False, comment="文档标题")
    file_path: Mapped[str] = mapped_column(String(512), nullable=False, comment="文件路径")
    file_name: Mapped[str] = mapped_column(String(256), nullable=False, comment="文件名")
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="文件大小(bytes)")
    uploader: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="上传人")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), comment="创建时间")

    system: Mapped["BusinessSystem"] = relationship("BusinessSystem", back_populates="documents", lazy="selectin")

    def __repr__(self) -> str:
        return f"<SystemDocument {self.title}>"
