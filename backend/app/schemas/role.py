"""角色相关 Pydantic Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PermissionInfo(BaseModel):
    id: int
    name: str
    code: str
    module: str
    model_config = {"from_attributes": True}


class RoleResponse(BaseModel):
    id: int
    name: str
    code: str
    description: Optional[str] = None
    is_builtin: bool
    created_at: datetime
    updated_at: datetime
    permissions: list[PermissionInfo] = []
    model_config = {"from_attributes": True}


class RoleCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=64, description="角色名称")
    code: str = Field(..., min_length=2, max_length=64, description="角色编码")
    description: Optional[str] = Field(None, max_length=256, description="角色描述")
    permissions: list[int] = Field(default_factory=list, description="权限ID列表")


class RoleUpdateRequest(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=64, description="角色名称")
    description: Optional[str] = Field(None, max_length=256, description="角色描述")
    permissions: Optional[list[int]] = Field(None, description="权限ID列表")
