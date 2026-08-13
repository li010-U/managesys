"""审计日志相关 Pydantic Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, computed_field


class AuditLogResponse(BaseModel):
    """审计日志响应"""
    id: int
    user_id: Optional[int] = None
    username: str
    action: str = Field(description="操作类型: login/logout/create/update/delete/export/mount/unmount/move")
    target_type: str = Field(description="操作对象类型: user/role/device/room/rack/system/alert/...")
    target_id: Optional[str] = None
    detail: Optional[str] = None
    ip_address: Optional[str] = None
    request_path: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}

    @computed_field
    @property
    def location(self) -> str:
        """IP 归属/分类标签（内网、公网、回环等）。"""
        from app.core.iputils import location_label
        return location_label(self.ip_address)


class AuditLogPageResponse(BaseModel):
    """审计日志分页响应"""
    items: list[AuditLogResponse]
    total: int
    page: int
    page_size: int


class AuditCountItem(BaseModel):
    """统计单项"""
    name: str
    count: int


class AuditSummaryResponse(BaseModel):
    """审计统计"""
    total: int
    by_action: list[AuditCountItem] = []
    by_target: list[AuditCountItem] = []
    by_user: list[AuditCountItem] = []
    trend: list[dict] = []


class AuditLogQuery(BaseModel):
    """审计日志查询参数"""
    keyword: Optional[str] = Field(None, description="搜索关键词(用户名/操作详情)")
    action: Optional[str] = Field(None, description="操作类型筛选")
    target_type: Optional[str] = Field(None, description="对象类型筛选")
    username: Optional[str] = Field(None, description="操作用户筛选")
    start_date: Optional[datetime] = Field(None, description="开始时间")
    end_date: Optional[datetime] = Field(None, description="结束时间")
