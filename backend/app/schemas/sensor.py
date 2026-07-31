"""传感器管理 Pydantic Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class SensorBase(BaseModel):
    room_id: int = Field(..., description="所属机房ID")
    name: str = Field(..., min_length=1, max_length=64, description="传感器名称")
    code: str = Field(..., min_length=1, max_length=64, description="传感器编号")
    sensor_type: str = Field(..., description="类型：temperature/humidity/smoke/water/door_magnetic")
    install_position: Optional[str] = Field(None, max_length=128)
    status: str = Field("offline", description="状态：online/offline")
    threshold_min: Optional[float] = Field(None, description="阈值下限")
    threshold_max: Optional[float] = Field(None, description="阈值上限")
    alert_level: str = Field("general", description="告警级别：general/serious/emergency")

class SensorCreate(SensorBase):
    pass

class SensorUpdate(BaseModel):
    name: Optional[str] = None
    sensor_type: Optional[str] = None
    install_position: Optional[str] = None
    status: Optional[str] = None
    threshold_min: Optional[float] = None
    threshold_max: Optional[float] = None
    alert_level: Optional[str] = None

class SensorResponse(SensorBase):
    id: int
    current_value: Optional[dict] = None
    last_update_time: Optional[datetime] = None
    room_name: str = ""
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class SensorPageResponse(BaseModel):
    items: list[SensorResponse]
    total: int
    page: int
    page_size: int

class SensorDataResponse(BaseModel):
    id: int
    sensor_id: int
    value: float
    recorded_at: datetime
    model_config = {"from_attributes": True}
