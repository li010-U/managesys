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
    source_mark: str = "normal"
    model_config = {"from_attributes": True}


class SensorAnomalyGapResponse(BaseModel):
    id: int
    sensor_id: int
    sensor_name: Optional[str] = None
    alert_id: Optional[int] = None
    detected_at: datetime
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    anomaly_type: str = "between_points_breach"
    severity: str = "warning"
    remark: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class RetentionResultResponse(BaseModel):
    days: int
    buffer_days: int
    cutoff: Optional[str] = None
    sensor_data_deleted: int = 0
    anomaly_gap_deleted: int = 0
    anomaly_gap_reconciled: int = 0

class RetentionStatusResponse(BaseModel):
    retention_days: int
    buffer_days: int
    task_enabled: bool
    cutoff: Optional[str] = None
    sensor_data_count: int = 0
    sensor_data_oldest: Optional[datetime] = None
    sensor_data_newest: Optional[datetime] = None
    anomaly_gap_count: int = 0
    anomaly_gap_oldest: Optional[datetime] = None
    anomaly_gap_newest: Optional[datetime] = None
