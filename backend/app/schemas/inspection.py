"""设备巡检 Schema"""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field


# ============ 巡检模板 ============
class InspectionTemplateBase(BaseModel):
    name: str = Field(..., max_length=128, description="模板名称")
    description: Optional[str] = Field(None, description="模板描述")
    device_type_id: Optional[int] = Field(None, description="适用的设备类型")
    items: Optional[list] = Field(None, description="巡检项配置")


class InspectionTemplateCreate(InspectionTemplateBase):
    pass


class InspectionTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = None
    device_type_id: Optional[int] = None
    items: Optional[list] = None


class InspectionTemplateResponse(InspectionTemplateBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============ 巡检计划 ============
class InspectionPlanBase(BaseModel):
    name: str = Field(..., max_length=128, description="计划名称")
    description: Optional[str] = Field(None, description="计划描述")
    plan_type: str = Field("periodic", description="计划类型: periodic/one_time")
    frequency: str = Field("daily", description="周期: daily/weekly/monthly")
    weekdays: Optional[str] = Field(None, description="执行星期")
    day_of_month: Optional[int] = Field(None, description="每月几号")
    execute_time: str = Field("09:00", description="执行时间")
    facility_id: Optional[int] = Field(None, description="关联机房")
    template_id: Optional[int] = Field(None, description="关联模板")
    assignee_id: Optional[int] = Field(None, description="巡检人")


class InspectionPlanCreate(InspectionPlanBase):
    pass


class InspectionPlanUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = None
    plan_type: Optional[str] = None
    frequency: Optional[str] = None
    weekdays: Optional[str] = None
    day_of_month: Optional[int] = None
    execute_time: Optional[str] = None
    facility_id: Optional[int] = None
    template_id: Optional[int] = None
    assignee_id: Optional[int] = None
    status: Optional[str] = None


class InspectionPlanResponse(InspectionPlanBase):
    id: int
    status: str
    next_execute_date: Optional[date] = None
    last_execute_date: Optional[date] = None
    template_name: Optional[str] = None
    facility_name: Optional[str] = None
    assignee_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InspectionPlanListResponse(BaseModel):
    id: int
    name: str
    plan_type: str
    frequency: str
    status: str
    facility_name: Optional[str] = None
    template_name: Optional[str] = None
    assignee_name: Optional[str] = None
    next_execute_date: Optional[date] = None
    last_execute_date: Optional[date] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ 巡检任务 ============
class InspectionTaskBase(BaseModel):
    facility_id: Optional[int] = Field(None, description="关联机房")


class InspectionTaskResponse(BaseModel):
    id: int
    plan_id: int
    plan_name: str
    facility_id: Optional[int] = None
    facility_name: Optional[str] = None
    status: str
    priority: str
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    scheduled_date: date
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_items: int
    completed_items: int
    abnormal_items: int
    remark: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    record_count: int = 0

    class Config:
        from_attributes = True


class InspectionTaskListResponse(BaseModel):
    id: int
    plan_id: int
    plan_name: str
    status: str
    priority: str
    assignee_name: Optional[str] = None
    facility_name: Optional[str] = None
    scheduled_date: date
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    total_items: int
    completed_items: int
    abnormal_items: int
    created_at: datetime

    class Config:
        from_attributes = True


# ============ 巡检记录 ============
class InspectionRecordCreate(BaseModel):
    device_id: Optional[int] = Field(None, description="关联设备")
    item_name: str = Field(..., description="巡检项名称")
    item_key: str = Field(..., description="巡检项标识")
    check_content: str = Field(..., description="检查内容")
    check_result: Optional[str] = Field("normal", description="检查结果: normal/abnormal/na")
    check_value: Optional[str] = Field(None, description="检查值")
    check_remark: Optional[str] = Field(None, description="检查备注")


class InspectionRecordResponse(BaseModel):
    id: int
    task_id: int
    device_id: Optional[int] = None
    device_name: Optional[str] = None
    item_name: str
    item_key: str
    check_content: str
    check_result: Optional[str] = None
    check_value: Optional[str] = None
    check_remark: Optional[str] = None
    inspector_id: int
    inspector_name: Optional[str] = None
    checked_at: datetime

    class Config:
        from_attributes = True


# ============ 巡检问题 ============
class InspectionIssueBase(BaseModel):
    device_id: Optional[int] = Field(None, description="关联设备")
    issue_title: str = Field(..., description="问题标题")
    issue_description: Optional[str] = Field(None, description="问题描述")
    severity: str = Field("normal", description="严重程度")


class InspectionIssueCreate(InspectionIssueBase):
    record_id: Optional[int] = Field(None, description="关联记录")


class InspectionIssueUpdate(BaseModel):
    issue_title: Optional[str] = Field(None, description="问题标题")
    issue_description: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    handler_id: Optional[int] = Field(None, description="处理人")
    resolve_content: Optional[str] = Field(None, description="处理内容")


class InspectionIssueResponse(InspectionIssueBase):
    id: int
    task_id: int
    record_id: Optional[int] = None
    status: str
    reporter_id: int
    reporter_name: Optional[str] = None
    handler_id: Optional[int] = None
    handler_name: Optional[str] = None
    device_name: Optional[str] = None
    resolve_content: Optional[str] = None
    resolve_time: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class InspectionIssueListResponse(BaseModel):
    id: int
    task_id: int
    task_name: Optional[str] = None
    device_name: Optional[str] = None
    issue_title: str
    severity: str
    status: str
    reporter_name: Optional[str] = None
    handler_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ============ 统计 ============
class InspectionStats(BaseModel):
    plan_count: int = 0
    active_plan_count: int = 0
    task_today: int = 0
    task_overdue: int = 0
    task_completed: int = 0
    issue_open: int = 0
    issue_resolved: int = 0
