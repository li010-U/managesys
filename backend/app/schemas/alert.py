"""告警 Schema"""
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional, Literal

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
    model_config = ConfigDict(from_attributes=True)

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
    model_config = ConfigDict(from_attributes=True)

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
    # ==== 智能告警增强：收敛/升级 ====
    dedupe_key: Optional[str] = None
    occurrences: Optional[int] = 1
    first_seen_at: Optional[datetime] = None
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    escalated_from: Optional[str] = None
    # ==== 告警生命周期（自动恢复/去重防抖/偶发故障） ====
    last_abnormal_at: Optional[datetime] = None
    normal_since_at: Optional[datetime] = None
    auto_resolve_minutes: Optional[int] = 30
    duration_seconds: Optional[int] = None
    is_transient: Optional[bool] = False
    cooldown_until: Optional[datetime] = None
    lifecycle_action: Optional[str] = None

class AlertPageResponse(BaseModel):
    items: list[AlertResponse]
    total: int
    page: int
    page_size: int

class AlertHandleRequest(BaseModel):
    action_type: Literal["acknowledge", "resolve", "ignore"] = Field(..., description="acknowledge/resolve/ignore")
    operator: Optional[str] = None
    remark: Optional[str] = None
    root_cause: Optional[str] = None

class AlertCreateRequest(BaseModel):
    target_type: Literal["device", "sensor", "system", "rack", "room"] = Field(..., max_length=32, description="告警对象类型")
    target_id: str = Field(..., max_length=64, description="告警对象ID")
    title: str = Field(..., max_length=256, description="告警标题")
    description: Optional[str] = Field(None, max_length=2000, description="告警描述")
    level: Literal["general", "serious", "emergency"] = "general"
    source: Literal["sensor", "monitor", "system", "manual"] = "system"
    device_id: Optional[int] = None

