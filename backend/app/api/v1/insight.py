# -*- coding: utf-8 -*-
"""智能分析 API：自学习基线、趋势预测、容量规划、可靠性、AI 巡检、告警智能、LLM 追溯。"""
from typing import Optional
from fastapi import APIRouter, Depends, Request, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission
from app.models.user import User
from app.services.insight_service import InsightService
from app.services.alert_intelligence_service import AlertIntelligenceService
from app.services.inspection_ai_service import InspectionAIService

router = APIRouter(prefix="/insight", tags=["智能分析"])


@router.get("/baseline/{sensor_id}")
async def sensor_baseline(
    sensor_id: int,
    lookback_days: int = Query(30, ge=1, le=180),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_dashboard")),
):
    """自学习基线：按小时槽的 IQR/Z-score 区间与当前值偏离评估。"""
    svc = InsightService(db)
    return await svc.sensor_baseline(sensor_id, lookback_days)


@router.get("/forecast/{sensor_id}")
async def sensor_forecast(
    sensor_id: int,
    lookback: int = Query(120, ge=3, le=500),
    horizon: int = Query(6, ge=1, le=24),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_dashboard")),
):
    """短时趋势预测：对传感器数值序列做线性回归，返回未来 N 步预测与区间。"""
    svc = InsightService(db)
    return await svc.sensor_forecast(sensor_id, lookback, horizon)


@router.get("/capacity")
async def rack_capacity(
    room_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_dashboard")),
):
    """机柜容量规划：U 位占用 + 供电负载 + 满载时间预估。"""
    svc = InsightService(db)
    return await svc.rack_capacity(room_id)


@router.get("/reliability")
async def reliability(
    room_id: Optional[int] = Query(None),
    days: int = Query(90, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_dashboard")),
):
    """可靠性指标：MTTR/MTBF/可用率。"""
    svc = InsightService(db)
    return await svc.reliability(room_id, days)


@router.get("/trace")
async def alert_trace(
    q: str = Query(..., description="自然语言追溯查询，如'某设备上周为何告警'"),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_dashboard")),
):
    """LLM 数据追溯：回溯告警生命周期、同类复发、Top 频发对象。"""
    svc = InsightService(db)
    return await svc.alert_trace(q, limit)


# ---------------- 告警智能 ----------------
@router.post("/alerts/escalate")
async def alerts_auto_escalate(
    request: Request,
    minutes: int = Query(30, ge=1, le=1440),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("monitor:handle_alert")),
):
    """手动触发一次未确认 emergency 告警的自动升级扫描。"""
    svc = AlertIntelligenceService(db, escalate_after_minutes=minutes)
    ids = await svc.auto_escalate()
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="execute", target_type="alert", detail=f"自动升级{minutes}分钟以上告警 ({len(ids)}条)")
    return {"escalated_count": len(ids), "escalated_ids": ids}


@router.post("/alerts/{alert_id}/converge")
async def converge_alert(
    alert_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("monitor:handle_alert")),
):
    """对某条告警执行收敛归并（同类开放告警叠加 occurrences）。"""
    from app.models.alert import Alert
    alert = (await db.get(Alert, alert_id))
    if alert is None:
        raise HTTPException(404, "告警不存在")
    svc = AlertIntelligenceService(db)
    result = await svc.converge_new_alert(alert)
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="execute", target_type="alert", target_id=str(alert_id), detail="收敛告警")
    return {"represents_alert_id": result.id, "occurrences": result.occurrences}


@router.get("/correlate/{room_id}")
async def correlate_room(
    room_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_dashboard")),
):
    """机房告警根因关联：聚合开放告警并给出根因提示。"""
    svc = AlertIntelligenceService(db)
    return await svc.correlate_room(room_id)


# ---------------- AI 巡检 ----------------
@router.get("/inspection/{room_id}")
async def inspection_checklist(
    room_id: int,
    days: int = Query(7, ge=1, le=90),
    with_llm: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_dashboard")),
):
    """AI 辅助巡检：根据机房近期告警/趋势生成重点检查清单。"""
    svc = InspectionAIService(db, with_llm=with_llm)
    return await svc.generate_checklist(room_id, days)