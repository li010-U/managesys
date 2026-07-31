"""告警管理 API 路由"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.alert_service import AlertRuleService, AlertService
from app.schemas.alert import (
    AlertRuleCreate, AlertRuleUpdate, AlertRuleResponse, AlertRulePageResponse,
    AlertResponse, AlertPageResponse, AlertHandleRequest,
)

router = APIRouter(prefix="/alerts", tags=["告警管理"])


# ==================== Alert Rules ====================

@router.get("/rules", response_model=AlertRulePageResponse)
async def list_alert_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str = Query(None),
    enabled: bool = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    service = AlertRuleService(db)
    items, total = await service.get_list(page, page_size, keyword, enabled)
    resp = []
    for item in items:
        r = AlertRuleResponse.model_validate(item)
        r.alert_count = len(item.alerts) if item.alerts else 0
        resp.append(r)
    return AlertRulePageResponse(items=resp, total=total, page=page, page_size=page_size)


@router.post("/rules", response_model=AlertRuleResponse, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    req: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    service = AlertRuleService(db)
    try:
        obj = await service.create(req)
        return AlertRuleResponse.model_validate(obj)
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: int,
    req: AlertRuleUpdate,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    service = AlertRuleService(db)
    obj = await service.update(rule_id, req)
    if not obj:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="规则不存在")
    r = AlertRuleResponse.model_validate(obj)
    r.alert_count = len(obj.alerts) if obj.alerts else 0
    return r


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    service = AlertRuleService(db)
    if not await service.delete(rule_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="规则不存在")
    return {"message": "规则已删除"}


# ==================== Alerts ====================

@router.get("", response_model=AlertPageResponse)
async def list_alerts(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str = Query(None),
    level: str = Query(None),
    status: str = Query(None),
    target_type: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    service = AlertService(db)
    items, total = await service.get_list(page, page_size, keyword, level, status, target_type)
    resp = []
    for item in items:
        r = AlertResponse.model_validate(item)
        if item.rule:
            r.rule_name = item.rule.name
        resp.append(r)
    return AlertPageResponse(items=resp, total=total, page=page, page_size=page_size)


@router.get("/stats")
async def alert_stats(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    service = AlertService(db)
    return await service.get_stats()


@router.put("/{alert_id}/handle")
async def handle_alert(
    alert_id: int,
    req: AlertHandleRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AlertService(db)
    alert = await service.handle(alert_id, req.model_dump(), current_user.username)
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="告警不存在")
    return {"message": "处理成功", "status": alert.status}


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    req: dict,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    service = AlertService(db)
    obj = await service.create(req)
    r = AlertResponse.model_validate(obj)
    return r
