"""工单相关 Schema"""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field


# ============ 工单分类 ============
class WorkOrderCategoryBase(BaseModel):
    name: str = Field(..., max_length=64, description="分类名称")
    code: str = Field(..., max_length=32, description="分类编码")
    icon: Optional[str] = Field(None, max_length=32, description="图标")
    sort: int = Field(0, description="排序")


class WorkOrderCategoryCreate(WorkOrderCategoryBase):
    pass


class WorkOrderCategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=64)
    code: Optional[str] = Field(None, max_length=32)
    icon: Optional[str] = Field(None, max_length=32)
    sort: Optional[int] = None


class WorkOrderCategoryResponse(WorkOrderCategoryBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============ 工单评论 ============
class WorkOrderCommentBase(BaseModel):
    content: str = Field(..., description="评论内容")
    comment_type: str = Field("normal", description="类型: normal/process/verify/close")


class WorkOrderCommentCreate(WorkOrderCommentBase):
    pass


class WorkOrderCommentResponse(WorkOrderCommentBase):
    id: int
    work_order_id: int
    user_id: int
    user_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ 工单附件 ============
class WorkOrderAttachmentResponse(BaseModel):
    id: int
    work_order_id: int
    file_name: str
    file_path: str
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    uploader_id: int
    uploader_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ 工单 ============
class WorkOrderBase(BaseModel):
    title: str = Field(..., max_length=256, description="工单标题")
    description: Optional[str] = Field(None, description="工单描述")
    category_id: Optional[int] = Field(None, description="工单分类")
    priority: str = Field("normal", description="优先级: low/normal/high/urgent")
    device_id: Optional[int] = Field(None, description="关联设备")
    facility_id: Optional[int] = Field(None, description="关联机房")
    plan_date: Optional[date] = Field(None, description="计划完成日期")
    estimated_hours: Optional[float] = Field(None, description="预估工时")


class WorkOrderCreate(WorkOrderBase):
    assignee_id: Optional[int] = Field(None, description="指定处理人")


class WorkOrderUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=256)
    description: Optional[str] = None
    category_id: Optional[int] = None
    priority: Optional[str] = None
    device_id: Optional[int] = None
    facility_id: Optional[int] = None
    plan_date: Optional[date] = None
    estimated_hours: Optional[float] = None


class WorkOrderAssign(BaseModel):
    assignee_id: int = Field(..., description="处理人ID")
    remark: Optional[str] = Field(None, description="备注")


class WorkOrderProcess(BaseModel):
    result: str = Field(..., description="处理结果")
    actual_hours: Optional[float] = Field(None, description="实际工时")


class WorkOrderVerify(BaseModel):
    satisfaction: int = Field(..., ge=1, le=5, description="满意度评分")
    feedback: Optional[str] = Field(None, description="用户反馈")
    accept: bool = Field(..., description="是否验收通过")


class WorkOrderClose(BaseModel):
    remark: Optional[str] = Field(None, description="关闭备注")


class WorkOrderStatusUpdate(BaseModel):
    status: str = Field(..., description="状态")


class WorkOrderResponse(WorkOrderBase):
    id: int
    order_no: str
    status: str
    creator_id: int
    creator_name: Optional[str] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    assignee_username: Optional[str] = None
    device_name: Optional[str] = None
    facility_name: Optional[str] = None
    category_name: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    actual_hours: Optional[float] = None
    result: Optional[str] = None
    satisfaction: Optional[int] = None
    feedback: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    comment_count: int = 0
    comments: List[WorkOrderCommentResponse] = []
    attachments: List[WorkOrderAttachmentResponse] = []

    class Config:
        from_attributes = True


class WorkOrderListResponse(BaseModel):
    id: int
    order_no: str
    title: str
    category_name: Optional[str] = None
    priority: str
    status: str
    creator_id: int
    creator_name: Optional[str] = None
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    device_name: Optional[str] = None
    facility_name: Optional[str] = None
    plan_date: Optional[date] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkOrderStats(BaseModel):
    total: int = 0
    pending: int = 0
    processing: int = 0
    completed: int = 0
    closed: int = 0
    my_pending: int = 0
    my_processing: int = 0
