"""业务系统 Schema"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class BusinessSystemCreate(BaseModel):
    name: str = Field(..., max_length=128)
    code: str = Field(..., max_length=64)
    category: str = "other"
    access_url: Optional[str] = None
    admin_name: Optional[str] = None
    admin_phone: Optional[str] = None
    admin_email: Optional[str] = None
    remark: Optional[str] = None
    status: str = "active"

class BusinessSystemUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    category: Optional[str] = None
    access_url: Optional[str] = None
    admin_name: Optional[str] = None
    admin_phone: Optional[str] = None
    admin_email: Optional[str] = None
    remark: Optional[str] = None
    status: Optional[str] = None

class BusinessSystemResponse(BaseModel):
    id: int
    name: str
    code: str
    category: str
    access_url: Optional[str]
    admin_name: Optional[str]
    admin_phone: Optional[str]
    admin_email: Optional[str]
    remark: Optional[str]
    status: str
    device_count: int = 0
    doc_count: int = 0
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class BusinessSystemPageResponse(BaseModel):
    items: list[BusinessSystemResponse]
    total: int
    page: int
    page_size: int

class DeploymentCreate(BaseModel):
    device_id: int
    service_port: Optional[str] = None
    process_name: Optional[str] = None
    system_version: Optional[str] = None
    middleware_version: Optional[str] = None

class DeploymentResponse(BaseModel):
    id: int; system_id: int; device_id: int; service_port: Optional[str]
    process_name: Optional[str]; system_version: Optional[str]; middleware_version: Optional[str]
    device_name: Optional[str] = None; created_at: datetime
    class Config:
        from_attributes = True
