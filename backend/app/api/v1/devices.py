"""设备管理 API 路由"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission, require_any_permission
from app.models.user import User
from app.services.device_service import DeviceTypeService, DeviceService
from app.schemas.device import (
    DeviceTypeCreate, DeviceTypeUpdate, DeviceTypeResponse, DeviceTypePageResponse,
    DeviceCreate, DeviceUpdate, DeviceResponse, DevicePageResponse,
    DeviceLifecycleResponse, ThresholdConfigUpdate,
)

router = APIRouter(prefix="/devices", tags=["设备管理"])


def get_client_ip(request: Request) -> str:
    """获取客户端真实IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


# ==================== DeviceType ====================

@router.get("/types", response_model=DeviceTypePageResponse)
async def list_device_types(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str = Query(None),
    category: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    service = DeviceTypeService(db)
    items, total = await service.get_list(page, page_size, keyword, category)
    resp = [DeviceTypeResponse.model_validate(dt) for dt in items]
    for i, dt in enumerate(items):
        resp[i].device_count = len(dt.devices or [])
    return DeviceTypePageResponse(items=resp, total=total, page=page, page_size=page_size)


@router.get("/types/all", response_model=list[DeviceTypeResponse])
async def list_all_device_types(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    service = DeviceTypeService(db)
    items = await service.get_all()
    return [DeviceTypeResponse.model_validate(dt) for dt in items]


@router.get("/types/{dt_id}", response_model=DeviceTypeResponse)
async def get_device_type(
    dt_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    service = DeviceTypeService(db)
    dt = await service.get_by_id(dt_id)
    if not dt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备类型不存在")
    r = DeviceTypeResponse.model_validate(dt)
    r.device_count = len(dt.devices or [])
    return r


@router.post("/types", response_model=DeviceTypeResponse, status_code=status.HTTP_201_CREATED)
async def create_device_type(
    req: DeviceTypeCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("device:create"))
):
    service = DeviceTypeService(db)
    try:
        dt = await service.create(
            req,
            operator_username=current_user.username,
            operator_ip=get_client_ip(request),
        )
        return DeviceTypeResponse.model_validate(dt)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/types/{dt_id}", response_model=DeviceTypeResponse)
async def update_device_type(
    dt_id: int,
    req: DeviceTypeUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("device:edit"))
):
    service = DeviceTypeService(db)
    dt = await service.update(
        dt_id, req,
        operator_username=current_user.username,
        operator_ip=get_client_ip(request),
    )
    if not dt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备类型不存在")
    r = DeviceTypeResponse.model_validate(dt)
    r.device_count = len(dt.devices or [])
    return r


@router.put("/types/{dt_id}/thresholds", response_model=DeviceTypeResponse)
async def update_device_type_thresholds(
    dt_id: int,
    req: ThresholdConfigUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("device:edit"))
):
    """更新设备类型传感器阈值配置"""
    service = DeviceTypeService(db)
    dt = await service.update_thresholds(
        dt_id, req,
        operator_username=current_user.username,
        operator_ip=get_client_ip(request),
    )
    if not dt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备类型不存在")
    r = DeviceTypeResponse.model_validate(dt)
    r.device_count = len(dt.devices or [])
    return r


@router.delete("/types/{dt_id}")
async def delete_device_type(
    dt_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("device:delete"))
):
    service = DeviceTypeService(db)
    try:
        if not await service.delete(
            dt_id,
            operator_username=current_user.username,
            operator_ip=get_client_ip(request),
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备类型不存在")
        return {"message": "设备类型已删除"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==================== Device ====================

@router.get("", response_model=DevicePageResponse)
async def list_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str = Query(None),
    device_type_id: int = Query(None),
    rack_id: int = Query(None),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    service = DeviceService(db)
    items, total = await service.get_list(page, page_size, keyword, device_type_id, rack_id, status)
    resp = []
    for d in items:
        r = DeviceResponse.model_validate(d)
        r.device_type_name = d.device_type.name if d.device_type else ""
        r.device_type_category = d.device_type.category if d.device_type else ""
        r.rack_name = d.rack.name if d.rack else ""
        r.room_name = d.rack.room.name if d.rack and d.rack.room else ""
        resp.append(r)
    return DevicePageResponse(items=resp, total=total, page=page, page_size=page_size)


@router.get("/{device_id}", response_model=DeviceResponse)
async def get_device(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    service = DeviceService(db)
    d = await service.get_by_id(device_id)
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    r = DeviceResponse.model_validate(d)
    r.device_type_name = d.device_type.name if d.device_type else ""
    r.device_type_category = d.device_type.category if d.device_type else ""
    r.rack_name = d.rack.name if d.rack else ""
    r.room_name = d.rack.room.name if d.rack and d.rack.room else ""
    return r


@router.post("", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
async def create_device(
    req: DeviceCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("device:create"))
):
    service = DeviceService(db)
    try:
        d = await service.create(
            req,
            operator_username=current_user.username,
            operator_ip=get_client_ip(request),
        )
        r = DeviceResponse.model_validate(d)
        r.device_type_name = d.device_type.name if d.device_type else ""
        r.device_type_category = d.device_type.category if d.device_type else ""
        r.rack_name = d.rack.name if d.rack else ""
        r.room_name = d.rack.room.name if d.rack and d.rack.room else ""
        return r
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{device_id}", response_model=DeviceResponse)
async def update_device(
    device_id: int,
    req: DeviceUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("device:edit"))
):
    service = DeviceService(db)
    d = await service.update(
        device_id, req,
        operator_username=current_user.username,
        operator_ip=get_client_ip(request),
    )
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    r = DeviceResponse.model_validate(d)
    r.device_type_name = d.device_type.name if d.device_type else ""
    r.device_type_category = d.device_type.category if d.device_type else ""
    r.rack_name = d.rack.name if d.rack else ""
    r.room_name = d.rack.room.name if d.rack and d.rack.room else ""
    return r


@router.delete("/{device_id}")
async def delete_device(
    device_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("device:delete"))
):
    service = DeviceService(db)
    if not await service.delete(
        device_id,
        operator_username=current_user.username,
        operator_ip=get_client_ip(request),
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    return {"message": "设备已删除"}


@router.put("/{device_id}/status")
async def change_device_status(
    device_id: int,
    status: str = Query(..., description="新状态"),
    operator: str = Query(None),
    remark: str = Query(None),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_any_permission("device:mount", "device:unmount", "device:edit"))
):
    service = DeviceService(db)
    client_ip = get_client_ip(request) if request else None
    d = await service.change_status(
        device_id, status, operator, remark,
        operator_username=current_user.username,
        operator_ip=client_ip,
    )
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    return {"message": "状态已更新", "status": d.status}


@router.get("/{device_id}/lifecycles", response_model=list[DeviceLifecycleResponse])
async def get_device_lifecycles(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    service = DeviceService(db)
    lcs = await service.get_lifecycles(device_id)
    return [DeviceLifecycleResponse.model_validate(lc) for lc in lcs]
