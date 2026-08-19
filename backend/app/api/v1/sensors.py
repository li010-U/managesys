"""传感器管理 API 路由"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission
from app.models.user import User
from app.services.sensor_service import SensorService
from app.schemas.sensor import (
    SensorCreate, SensorUpdate, SensorResponse, SensorPageResponse, SensorDataResponse,
    SensorAnomalyGapResponse, RetentionResultResponse, RetentionStatusResponse,
)
from app.models.sensor import SensorAnomalyGap, SensorData
from app.services.sensor_anomaly_service import SensorAnomalyService
from app.core.config import settings
from sqlalchemy import select, func

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


@router.get("/{sensor_id:int}", response_model=SensorResponse)
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("device:create"))
):
    service = SensorService(db)
    try:
        s = await service.create(req)
        from app.services.audit_service import AuditService
        AuditService.log_request(db, request, current_user=current_user, action="create", target_type="sensor", target_id=str(s.id), detail=f"创建传感器: {s.name}")
        r = SensorResponse.model_validate(s)
        if hasattr(s, "room") and s.room:
            r.room_name = s.room.name
        return r
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{sensor_id:int}", response_model=SensorResponse)
async def update_sensor(
    sensor_id: int,
    req: SensorUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("device:edit"))
):
    service = SensorService(db)
    s = await service.update(sensor_id, req)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="传感器不存在")
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="update", target_type="sensor", target_id=str(sensor_id), detail=f"更新传感器: {s.name}")
    r = SensorResponse.model_validate(s)
    if hasattr(s, "room") and s.room:
        r.room_name = s.room.name
    return r


@router.delete("/{sensor_id:int}")
async def delete_sensor(
    sensor_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("device:delete"))
):
    service = SensorService(db)
    if not await service.delete(sensor_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="传感器不存在")
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="delete", target_type="sensor", target_id=str(sensor_id), detail="删除传感器")
    return {"message": "传感器已删除"}


@router.get("/{sensor_id:int}/data", response_model=list[SensorDataResponse])
async def get_sensor_data(
    sensor_id: int,
    limit: int = Query(20, ge=1, le=1000),
    hours: float = Query(None, ge=0.1, le=24 * 30),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    """获取传感器历史数据。
    - limit: 返回点数上限（默认 20）。
    - hours: 可选，指定回溯时间窗口（小时）。设置后返回该窗口内完整数据，
      并对海量采样点自动降采样，供半天/一天等长周期趋势图展示。
    """
    service = SensorService(db)
    data = await service.get_recent_data(sensor_id, limit, hours=hours)
    return [SensorDataResponse.model_validate(d) for d in data]


@router.post("/{sensor_id:int}/data", response_model=SensorDataResponse)
async def record_sensor_data(
    request: Request,
    sensor_id: int,
    value: float = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("monitor:handle_alert"))
):
    service = SensorService(db)
    sd = await service.record_data(sensor_id, value)
    if sd is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="传感器不存在")
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="execute", target_type="sensor", target_id=str(sensor_id), detail="录入传感器数据")
    return SensorDataResponse.model_validate(sd)


@router.get("/anomaly-gaps", response_model=list[SensorAnomalyGapResponse])
async def list_anomaly_gaps(
    sensor_id: int = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    """查询"两采集点之间越阈但采集点正常"的异常留痕。"""
    stmt = select(SensorAnomalyGap).order_by(SensorAnomalyGap.detected_at.desc()).limit(limit)
    if sensor_id is not None:
        stmt = stmt.where(SensorAnomalyGap.sensor_id == sensor_id)
    rows = (await db.execute(stmt)).scalars().all()
    resp = []
    for r in rows:
        sr = SensorAnomalyGapResponse.model_validate(r)
        if r.sensor:
            sr.sensor_name = r.sensor.name
        resp.append(sr)
    return resp


@router.post("/retention", response_model=RetentionResultResponse)
async def run_retention(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动触发数据保留清理（滚动删除超期 sensor_data / 异常留痕），仅超级管理员。"""
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    svc = SensorAnomalyService(db)
    gap_added = await svc.reconcile_from_alerts(since=None)
    result = await svc.run_retention()
    result["anomaly_gap_reconciled"] = gap_added
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="execute", target_type="sensor", detail="执行传感器数据保留清理")
    return result


@router.get("/retention-status", response_model=RetentionStatusResponse)
async def retention_status(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    """查询数据保留配置与当前数据量（保留期内数据详情）。"""
    days = settings.DATA_RETENTION_DAYS
    buffer_days = settings.DATA_RETENTION_BUFFER_DAYS
    cutoff = datetime.now() - timedelta(days=days + buffer_days)

    sd_count = (await db.execute(select(func.count()).select_from(SensorData))).scalar() or 0
    sd_oldest = (await db.execute(select(func.min(SensorData.recorded_at)))).scalar()
    sd_newest = (await db.execute(select(func.max(SensorData.recorded_at)))).scalar()

    ag_count = (await db.execute(select(func.count()).select_from(SensorAnomalyGap))).scalar() or 0
    ag_oldest = (await db.execute(select(func.min(SensorAnomalyGap.detected_at)))).scalar()
    ag_newest = (await db.execute(select(func.max(SensorAnomalyGap.detected_at)))).scalar()

    return RetentionStatusResponse(
        retention_days=days,
        buffer_days=buffer_days,
        task_enabled=settings.DATA_RETENTION_TASK_ENABLED,
        cutoff=cutoff.isoformat(),
        sensor_data_count=sd_count,
        sensor_data_oldest=sd_oldest,
        sensor_data_newest=sd_newest,
        anomaly_gap_count=ag_count,
        anomaly_gap_oldest=ag_oldest,
        anomaly_gap_newest=ag_newest,
    )
