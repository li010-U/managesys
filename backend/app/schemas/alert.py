"""告警 Schema"""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class AlertRuleCreate(BaseModel):
    name: str = Field(..., max_length=128)
    code: str = Field(..., max_length=64)
    metric: str = Field(..., max_length=64)
    condition: str = Field(..., max_length=8)
    threshold: float
    alert_level: str = "general"
    enabled: bool = True
    notify_methods: Optional[list[str]] = None

class AlertRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    metric: Optional[str] = Field(None, max_length=64)
    condition: Optional[str] = Field(None, max_length=8)
    threshold: Optional[float] = None
    alert_level: Optional[str] = None
    enabled: Optional[bool] = None
    notify_methods: Optional[list[str]] = None

class AlertRuleResponse(BaseModel):
    id: int
    name: str
    code: str
    metric: str
    condition: str
    threshold: float
    alert_level: str
    enabled: bool
    notify_methods: Optional[list] = None
    alert_count: int = 0
    created_at: datetime
    updated_at: datetime

class AlertRulePageResponse(BaseModel):
    items: list[AlertRuleResponse]
    total: int
    page: int
    page_size: int

# Alert
class AlertResponse(BaseModel):
    id: int
    alert_rule_id: Optional[int]
    device_id: Optional[int]
    target_type: str
    target_id: str
    title: str
    description: Optional[str]
    level: str
    status: str
    source: str
    rule_name: Optional[str] = None
    device_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class AlertPageResponse(BaseModel):
    items: list[AlertResponse]
    total: int
    page: int
    page_size: int

class AlertHandleRequest(BaseModel):
    action_type: str = Field(..., description="acknowledge/resolve/ignore")
    operator: Optional[str] = None
    remark: Optional[str] = None
    root_cause: Optional[str] = None

class AlertCreateRequest(BaseModel):
    target_type: str
    target_id: str
    title: str
    description: Optional[str] = None
    level: str = "general"
    source: str = "system"
    device_id: Optional[int] = None
