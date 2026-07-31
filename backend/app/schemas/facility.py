"""机房管理 Pydantic Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ===== DataCenter =====
class DataCenterBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128, description="数据中心名称")
    code: str = Field(..., min_length=1, max_length=64, description="数据中心编码")
    address: Optional[str] = Field(None, max_length=256, description="地址")
    description: Optional[str] = Field(None, max_length=512, description="描述")
    contact_person: Optional[str] = Field(None, max_length=64, description="联系人")
    contact_phone: Optional[str] = Field(None, max_length=32, description="联系电话")
    contact_email: Optional[str] = Field(None, max_length=128, description="联系邮箱")
    status: str = Field("active", description="状态: active/disabled")


class DataCenterCreate(DataCenterBase):
    pass


class DataCenterUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    code: Optional[str] = Field(None, min_length=1, max_length=64)
    address: Optional[str] = Field(None, max_length=256)
    description: Optional[str] = Field(None, max_length=512)
    contact_person: Optional[str] = Field(None, max_length=64)
    contact_phone: Optional[str] = Field(None, max_length=32)
    contact_email: Optional[str] = Field(None, max_length=128)
    status: Optional[str] = None


class DataCenterResponse(DataCenterBase):
    id: int
    room_count: int = 0
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class DataCenterPageResponse(BaseModel):
    items: list[DataCenterResponse]
    total: int
    page: int
    page_size: int


# ===== Room =====
class RoomBase(BaseModel):
    data_center_id: int = Field(..., description="所属数据中心ID")
    name: str = Field(..., min_length=1, max_length=128, description="机房名称")
    code: str = Field(..., min_length=1, max_length=64, description="机房编号")
    floor: Optional[str] = Field(None, max_length=32, description="楼层")
    area: Optional[float] = Field(None, description="面积(平方米)")
    load_rating: Optional[str] = Field(None, max_length=32, description="承重等级(kg/平方米)")
    admin_name: Optional[str] = Field(None, max_length=64, description="管理员姓名")
    admin_phone: Optional[str] = Field(None, max_length=32, description="管理员电话")
    admin_email: Optional[str] = Field(None, max_length=128, description="管理员邮箱")
    tier_level: Optional[str] = Field(None, max_length=16, description="Tier等级: Tier I/Tier II/Tier III/Tier IV")
    description: Optional[str] = Field(None, max_length=512)
    status: str = Field("active", description="状态")


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    data_center_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=128)
    code: Optional[str] = Field(None, min_length=1, max_length=64)
    floor: Optional[str] = None
    area: Optional[float] = None
    load_rating: Optional[str] = None
    admin_name: Optional[str] = None
    admin_phone: Optional[str] = None
    admin_email: Optional[str] = None
    tier_level: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class RoomResponse(RoomBase):
    id: int
    rack_count: int = 0
    data_center_name: str = ""
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class RoomPageResponse(BaseModel):
    items: list[RoomResponse]
    total: int
    page: int
    page_size: int


# ===== Rack =====
class RackBase(BaseModel):
    room_id: int = Field(..., description="所属机房ID")
    name: str = Field(..., min_length=1, max_length=64, description="机柜名称")
    code: str = Field(..., min_length=1, max_length=64, description="机柜编号")
    row_pos: Optional[int] = Field(None, description="所在行")
    col_pos: Optional[int] = Field(None, description="所在列")
    total_units: int = Field(42, description="总U位数")
    rated_power: Optional[float] = Field(None, description="额定功率(kW)")
    description: Optional[str] = Field(None, max_length=512)


class RackCreate(RackBase):
    pass


class RackUpdate(BaseModel):
    room_id: Optional[int] = None
    name: Optional[str] = Field(None, min_length=1, max_length=64)
    code: Optional[str] = Field(None, min_length=1, max_length=64)
    row_pos: Optional[int] = None
    col_pos: Optional[int] = None
    total_units: Optional[int] = None
    rated_power: Optional[float] = None
    description: Optional[str] = None


class RackResponse(RackBase):
    id: int
    available_units: int
    device_count: int = 0
    room_name: str = ""
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class RackPageResponse(BaseModel):
    items: list[RackResponse]
    total: int
    page: int
    page_size: int
