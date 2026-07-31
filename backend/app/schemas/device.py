"""设备管理 Pydantic Schema"""
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, Field


# ===== 传感器阈值配置 =====
class ThresholdConfig(BaseModel):
    """传感器阈值配置"""
    metric: str = Field(..., description="监控指标: temperature/humidity/cpu_usage/memory_usage/disk_usage")
    label: str = Field(..., description="显示标签")
    min_value: Optional[float] = Field(None, description="最小值（警告下限）")
    max_value: Optional[float] = Field(None, description="最大值（警告上限）")
    unit: str = Field("%", description="单位")
    alert_level: str = Field("general", description="告警级别: general/serious/emergency")
    enabled: bool = Field(True, description="是否启用")


class ThresholdConfigUpdate(BaseModel):
    """阈值配置更新"""
    thresholds: list[ThresholdConfig]


# ===== DeviceType =====
class DeviceTypeBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=64, description="类型名称")
    code: str = Field(..., min_length=1, max_length=64, description="类型编码")
    category: str = Field(..., description="设备分类: server/network/storage/security/power")
    manufacturer: Optional[str] = Field(None, max_length=128, description="厂商")
    model: Optional[str] = Field(None, max_length=128, description="型号")
    spec_description: Optional[str] = Field(None, description="规格描述")


class DeviceTypeCreate(DeviceTypeBase):
    pass


class DeviceTypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    code: Optional[str] = Field(None, min_length=1, max_length=64)
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    spec_description: Optional[str] = None


class DeviceTypeResponse(DeviceTypeBase):
    id: int
    thresholds: Optional[dict] = None
    device_count: int = 0
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class DeviceTypePageResponse(BaseModel):
    items: list[DeviceTypeResponse]
    total: int
    page: int
    page_size: int


# ===== Device =====
class DeviceBase(BaseModel):
    device_type_id: int = Field(..., description="设备类型ID")
    rack_id: Optional[int] = Field(None, description="所在机柜ID")
    name: str = Field(..., min_length=1, max_length=128, description="设备名称")
    asset_number: str = Field(..., min_length=1, max_length=128, description="资产编号")
    serial_number: Optional[str] = Field(None, max_length=128, description="序列号")
    brand: Optional[str] = Field(None, max_length=64, description="品牌")
    model: Optional[str] = Field(None, max_length=128, description="型号")
    cpu_info: Optional[str] = Field(None, max_length=256)
    memory_info: Optional[str] = Field(None, max_length=256)
    disk_info: Optional[str] = Field(None, max_length=512)
    network_info: Optional[str] = Field(None, max_length=256)
    purchase_order: Optional[str] = Field(None, max_length=128)
    purchase_date: Optional[date] = None
    vendor: Optional[str] = Field(None, max_length=128)
    purchase_price: Optional[float] = None
    warranty_start: Optional[date] = None
    warranty_end: Optional[date] = None
    warranty_vendor: Optional[str] = Field(None, max_length=128)
    start_u: Optional[int] = None
    end_u: Optional[int] = None
    management_ip: Optional[str] = Field(None, max_length=64)
    business_ip: Optional[str] = Field(None, max_length=128)
    mac_address: Optional[str] = Field(None, max_length=64)
    out_of_band_ip: Optional[str] = Field(None, max_length=64)
    status: str = Field("in_stock", description="状态: in_stock/mounted/running/offline/scrapped")


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    device_type_id: Optional[int] = None
    rack_id: Optional[int] = None
    name: Optional[str] = None
    asset_number: Optional[str] = None
    serial_number: Optional[str] = None
    brand: Optional[str] = None
    model: Optional[str] = None
    cpu_info: Optional[str] = None
    memory_info: Optional[str] = None
    disk_info: Optional[str] = None
    network_info: Optional[str] = None
    purchase_order: Optional[str] = None
    purchase_date: Optional[date] = None
    vendor: Optional[str] = None
    purchase_price: Optional[float] = None
    warranty_start: Optional[date] = None
    warranty_end: Optional[date] = None
    warranty_vendor: Optional[str] = None
    start_u: Optional[int] = None
    end_u: Optional[int] = None
    management_ip: Optional[str] = None
    business_ip: Optional[str] = None
    mac_address: Optional[str] = None
    out_of_band_ip: Optional[str] = None
    status: Optional[str] = None


class DeviceResponse(DeviceBase):
    id: int
    device_type_name: str = ""
    device_type_category: str = ""
    rack_name: str = ""
    room_name: str = ""
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class DevicePageResponse(BaseModel):
    items: list[DeviceResponse]
    total: int
    page: int
    page_size: int


# ===== DeviceLifecycle =====
class DeviceLifecycleResponse(BaseModel):
    id: int
    device_id: int
    action: str
    from_status: Optional[str]
    to_status: str
    operator: Optional[str]
    remark: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}
