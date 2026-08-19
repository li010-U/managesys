# -*- coding: utf-8 -*-
"""告警生命周期与环境关联统计 API"""
from datetime import timedelta
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.config import settings
from app.core.deps import get_db, get_current_user, require_permission
from app.models.env_weather import EnvWeatherRecord, TransientFailureEvent
from app.models.user import User
from app.schemas.alert_lifecycle import (
    AlertSignalRequest,
    EnvWeatherRecordCreate,
    EnvWeatherRecordResponse,
    TransientEventResponse,
)
from app.services.alert_lifecycle_service import AlertLifecycleService
from app.services.environment_service import EnvWeatherService
from app.services.alert_report_service import AlertCorrelationReportService
from app.core.timeutil import now_local

router = APIRouter(prefix="/alert-lifecycle", tags=["告警生命周期"])


@router.post("/signal")
async def post_signal(
    req: AlertSignalRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("monitor:handle_alert")),
):
    """设备参数状态信号入口：异常/恢复，自动执行去重、防抖、偶发识别。"""
    svc = AlertLifecycleService(db)
    result = await svc.register_signal(
        target_type=req.target_type,
        target_id=req.target_id,
        is_abnormal=req.is_abnormal,
        title=req.title,
        level=req.level,
        device_id=req.device_id,
        metric=req.metric,
        source=req.source,
        observed_at=req.observed_at,
    )
    from app.services.audit_service import AuditService
    AuditService.log_request(
        db, request, current_user=current_user, action="execute",
        target_type="alert_lifecycle", target_id=req.target_id,
        detail=f"告警生命周期信号: {req.target_id} {'异常' if req.is_abnormal else '恢复'} -> {result['action']}",
    )
    return result


@router.post("/sweep")
async def run_sweep(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动触发自动恢复扫描（参数连续正常 30 分钟 -> 已解决）。"""
    if not current_user.is_super_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="权限不足")
    svc = AlertLifecycleService(db)
    resolved = await svc.sweep_auto_resolve()
    return {"resolved_count": len(resolved), "resolved_ids": resolved}


# ===== 环境/气象数据 =====

@router.post("/env", response_model=EnvWeatherRecordResponse, status_code=status.HTTP_201_CREATED)
async def record_env(
    req: EnvWeatherRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("monitor:handle_alert")),
):
    svc = EnvWeatherService(db)
    rec = await svc.record(**req.model_dump())
    return EnvWeatherRecordResponse.model_validate(rec)


@router.get("/env/recent", response_model=list[EnvWeatherRecordResponse])
async def recent_env(
    limit: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_alerts")),
):
    rows = (await db.execute(
        select(EnvWeatherRecord).order_by(EnvWeatherRecord.recorded_at.desc()).limit(limit)
    )).scalars().all()
    return [EnvWeatherRecordResponse.model_validate(r) for r in rows]


@router.get("/env/trend")
async def env_trend(
    hours: int = Query(24, ge=1, le=168),
    limit: int = Query(200, ge=10, le=1000),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_alerts")),
):
    """环境数据趋势序列（时间升序）：温度/湿度/风速，供前端折线图。"""
    env = EnvWeatherService(db)
    return await env.env_trend(hours=hours, limit=limit)


# ===== 偶发故障事件 =====

@router.get("/transient", response_model=list[TransientEventResponse])
async def list_transient(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_alerts")),
):
    rows = (await db.execute(
        select(TransientFailureEvent).order_by(TransientFailureEvent.started_at.desc()).limit(limit)
    )).scalars().all()
    svc = EnvWeatherService(db)
    for r in rows:
        await svc.attach_nearest_env(r)
    return [TransientEventResponse.model_validate(r) for r in rows]


# ===== 关联统计 =====

@router.get("/correlation")
async def correlation(
    days: int = Query(None, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_alerts")),
):
    env = EnvWeatherService(db)
    since = now_local() - timedelta(days=days) if days else None
    data = await env.correlation_report(days=days or settings.ENV_RETENTION_DAYS)
    return data


@router.get("/correlation/report", response_class=HTMLResponse)
async def correlation_report_html(
    days: int = Query(None, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_alerts")),
):
    """生成可独立打开的 HTML 可视化关联报表。"""
    svc = AlertCorrelationReportService(db)
    data = await svc.build(days=days)
    return HTMLResponse(content=svc.render_html(data))
