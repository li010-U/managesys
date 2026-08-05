"""传感器管理 API 路由"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission
from app.models.user import User
from app.services.sensor_service import SensorService
from app.schemas.sensor import (
    SensorCreate, SensorUpdate, SensorResponse, SensorPageResponse, SensorDataResponse,
)

router = APIRouter(prefix="/sensors", tags=["环境监测"])


@router.get("", response_model=SensorPageResponse)
async def list_sensors(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    room_id: int = Query(None),
    sensor_type: str = Query(None),
    keyword: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    service = SensorService(db)
    items, total = await service.get_list(page, page_size, room_id, sensor_type, keyword)
    resp = []
    for s in items:
        r = SensorResponse.model_validate(s)
        if hasattr(s, "room") and s.room:
            r.room_name = s.room.name
        resp.append(r)
    return SensorPageResponse(items=resp, total=total, page=page, page_size=page_size)


@router.get("/all", response_model=list[SensorResponse])
async def list_all_sensors(
    room_id: int = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    service = SensorService(db)
    items = await service.get_all(room_id)
    resp = []
    for s in items:
        r = SensorResponse.model_validate(s)
        if hasattr(s, "room") and s.room:
            r.room_name = s.room.name
        resp.append(r)
    return resp


@router.get("/{sensor_id}", response_model=SensorResponse)
async def get_sensor(
    sensor_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    service = SensorService(db)
    s = await service.get_by_id(sensor_id)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="传感器不存在")
    r = SensorResponse.model_validate(s)
    if hasattr(s, "room") and s.room:
        r.room_name = s.room.name
    return r


@router.post("", response_model=SensorResponse, status_code=status.HTTP_201_CREATED)
async def create_sensor(
    req: SensorCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("device:create"))
):
    service = SensorService(db)
    try:
        s = await service.create(req)
        r = SensorResponse.model_validate(s)
        if hasattr(s, "room") and s.room:
            r.room_name = s.room.name
        return r
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{sensor_id}", response_model=SensorResponse)
async def update_sensor(
    sensor_id: int,
    req: SensorUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("device:edit"))
):
    service = SensorService(db)
    s = await service.update(sensor_id, req)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="传感器不存在")
    r = SensorResponse.model_validate(s)
    if hasattr(s, "room") and s.room:
        r.room_name = s.room.name
    return r


@router.delete("/{sensor_id}")
async def delete_sensor(
    sensor_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("device:delete"))
):
    service = SensorService(db)
    if not await service.delete(sensor_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="传感器不存在")
    return {"message": "传感器已删除"}


@router.get("/{sensor_id}/data", response_model=list[SensorDataResponse])
async def get_sensor_data(
    sensor_id: int,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    service = SensorService(db)
    data = await service.get_recent_data(sensor_id, limit)
    return [SensorDataResponse.model_validate(d) for d in data]


@router.post("/{sensor_id}/data", response_model=SensorDataResponse)
async def record_sensor_data(
    sensor_id: int,
    value: float = Query(...),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("monitor:handle_alert"))
):
    service = SensorService(db)
    sd = await service.record_data(sensor_id, value)
    return SensorDataResponse.model_validate(sd)
