"""用户相关 Pydantic Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class RoleInfo(BaseModel):
    id: int
    name: str
    code: str
    permission_codes: list[str] = []
    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: int
    username: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    position: Optional[str] = None
    is_active: bool
    is_super_admin: bool
    last_login: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    roles: list[RoleInfo] = []
    model_config = {"from_attributes": True}


class UserCreateRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64, description="用户名")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    real_name: Optional[str] = Field(None, max_length=64, description="真实姓名")
    email: Optional[str] = Field(None, max_length=128, description="邮箱")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    department: Optional[str] = Field(None, max_length=128, description="部门")
    position: Optional[str] = Field(None, max_length=64, description="岗位")
    is_active: bool = Field(True, description="是否启用")
    roles: list[int] = Field(default_factory=list, description="角色ID列表")


class UserUpdateRequest(BaseModel):
    real_name: Optional[str] = Field(None, max_length=64, description="真实姓名")
    email: Optional[str] = Field(None, max_length=128, description="邮箱")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    department: Optional[str] = Field(None, max_length=128, description="部门")
    position: Optional[str] = Field(None, max_length=64, description="岗位")
    is_active: Optional[bool] = Field(None, description="是否启用")
    roles: Optional[list[int]] = Field(None, description="角色ID列表")


class UserPageResponse(BaseModel):
    items: list[UserResponse]
    total: int
    page: int
    page_size: int

