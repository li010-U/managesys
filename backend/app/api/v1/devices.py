"""设备管理 API 路由"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
import csv
import io
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission, require_any_permission
from app.core.iputils import request_client_ip
from app.models.user import User
from app.services.device_service import DeviceTypeService, DeviceService
from app.services.audit_service import AuditService
from app.schemas.device import (
    DeviceTypeCreate, DeviceTypeUpdate, DeviceTypeResponse, DeviceTypePageResponse,
    DeviceCreate, DeviceUpdate, DeviceResponse, DevicePageResponse,
    DeviceLifecycleResponse, ThresholdConfigUpdate,
)

router = APIRouter(prefix="/devices", tags=["设备管理"])


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
            operator_ip=request_client_ip(request),
        )
        AuditService.log_request(db, request, current_user=current_user, action="create", target_type="device_type", target_id=str(dt.id), detail=f"创建设备类型: {dt.name}")
        return DeviceTypeResponse.model_validate(dt)
    except ValueError as e:
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
        operator_ip=request_client_ip(request),
    )
    if not dt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备类型不存在")
    AuditService.log_request(db, request, current_user=current_user, action="update", target_type="device_type", target_id=str(dt.id), detail=f"更新设备类型: {dt.name}")
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
        operator_ip=request_client_ip(request),
    )
    if not dt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备类型不存在")
    AuditService.log_request(db, request, current_user=current_user, action="update", target_type="device_type", target_id=str(dt.id), detail=f"更新设备类型传感器阈值: {dt.name}")
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
            operator_ip=request_client_ip(request),
        ):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备类型不存在")
        AuditService.log_request(db, request, current_user=current_user, action="delete", target_type="device_type", target_id=str(dt_id), detail="删除设备类型")
        return {"message": "设备类型已删除"}
    except ValueError as e:
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
    sort_by: str = Query(None),
    order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    service = DeviceService(db)
    items, total = await service.get_list(page, page_size, keyword, device_type_id, rack_id, status, sort_by, order)
    resp = []
    for d in items:
        r = DeviceResponse.model_validate(d)
        r.device_type_name = d.device_type.name if d.device_type else ""
        r.device_type_category = d.device_type.category if d.device_type else ""
        r.rack_name = d.rack.name if d.rack else ""
        r.room_name = d.rack.room.name if d.rack and d.rack.room else ""
        resp.append(r)
    return DevicePageResponse(items=resp, total=total, page=page, page_size=page_size)


@router.get("/export", summary="导出设备列表 CSV")
async def export_devices(
    keyword: str = Query(None),
    device_type_id: int = Query(None),
    rack_id: int = Query(None),
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    """导出设备台账为 CSV（兼容 Excel 中文显示），应用当前列表筛选条件。"""
    service = DeviceService(db)
    items, _ = await service.get_list(1, 100000, keyword, device_type_id, rack_id, status)

    headers = ["ID",
               "名称",
               "资产编号",
               "序列号",
               "设备类型",
               "类型分类",
               "所在机柜",
               "所在机房",
               "状态",
               "管理IP",
               "业务IP",
               "创建时间"]
    buf = io.StringIO()
    buf.write("\ufeff")
    writer = csv.writer(buf)
    writer.writerow(headers)
    for d in items:
        writer.writerow([
            d.id, d.name, d.asset_number, d.serial_number or "",
            d.device_type.name if d.device_type else "",
            d.device_type.category if d.device_type else "",
            d.rack.name if d.rack else "",
            d.rack.room.name if d.rack and d.rack.room else "",
            d.status, d.management_ip or "", d.business_ip or "",
            d.created_at.strftime("%Y-%m-%d %H:%M:%S") if d.created_at else "",
        ])
    filename = f"devices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(content=buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})

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


@router.get("/{device_id}/environment")
async def get_device_environment(
    device_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    """设备⇄机房⇄传感器关联：返回该设备所在机房的传感器/环境快照。"""
    service = DeviceService(db)
    data = await service.get_device_environment(device_id)
    if data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    return data


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
            operator_ip=request_client_ip(request),
        )
        AuditService.log_request(db, request, current_user=current_user, action="create", target_type="device", target_id=str(d.id), detail=f"创建设备: {d.name}")
        r = DeviceResponse.model_validate(d)
        r.device_type_name = d.device_type.name if d.device_type else ""
        r.device_type_category = d.device_type.category if d.device_type else ""
        r.rack_name = d.rack.name if d.rack else ""
        r.room_name = d.rack.room.name if d.rack and d.rack.room else ""
        return r
    except ValueError as e:
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
        operator_ip=request_client_ip(request),
    )
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    AuditService.log_request(db, request, current_user=current_user, action="update", target_type="device", target_id=str(d.id), detail=f"更新设备: {d.name}")
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
        operator_ip=request_client_ip(request),
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    AuditService.log_request(db, request, current_user=current_user, action="delete", target_type="device", target_id=str(device_id), detail="删除设备")
    return {"message": "设备已删除"}


@router.put("/{device_id}/status")
async def change_device_status(
    device_id: int,
    status: str = Query(..., description="新状态"),
    remark: str = Query(None, max_length=256, description="备注(可选,最长256)"),
    request: Request = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_any_permission("device:mount", "device:unmount", "device:edit"))
):
    # 操作人一律以服务端认证用户为准，不接受客户端传入 operator，防止审计冒名
    service = DeviceService(db)
    client_ip = request_client_ip(request) if request else None
    d = await service.change_status(
        device_id, status, None, remark,
        operator_username=current_user.username,
        operator_ip=client_ip,
    )
    if not d:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备不存在")
    AuditService.log_request(db, request, current_user=current_user, action="change_status", target_type="device", target_id=str(d.id), detail=f"设备 {d.name} 状态变更 -> {d.status}")
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
