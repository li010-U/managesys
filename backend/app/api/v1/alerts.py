"""告警管理 API 路由"""
from fastapi import APIRouter, Depends, Query, status, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission
from app.core.config import settings
from app.core.ratelimit import user_rate_limit
from app.models.user import User
from app.services.alert_service import AlertRuleService, AlertService
from app.services.llm_service import llm_service
from app.services.assistant_service import get_cached_snapshot, AssistantService
from sqlalchemy import select
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
    _current_user: User = Depends(require_permission("monitor:view_alerts")),
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("monitor:config_rule"))
):
    service = AlertRuleService(db)
    try:
        obj = await service.create(req)
        from app.services.audit_service import AuditService
        AuditService.log_request(db, request, current_user=current_user, action="create", target_type="alert_rule", target_id=str(obj.id), detail=f"创建告警规则: {obj.name}")
        return AlertRuleResponse.model_validate(obj)
    except ValueError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/rules/{rule_id}", response_model=AlertRuleResponse)
async def update_alert_rule(
    rule_id: int,
    req: AlertRuleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("monitor:config_rule"))
):
    service = AlertRuleService(db)
    obj = await service.update(rule_id, req)
    if not obj:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="规则不存在")
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="update", target_type="alert_rule", target_id=str(rule_id), detail=f"更新告警规则: {obj.name}")
    r = AlertRuleResponse.model_validate(obj)
    r.alert_count = len(obj.alerts) if obj.alerts else 0
    return r


@router.delete("/rules/{rule_id}")
async def delete_alert_rule(
    rule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("monitor:config_rule"))
):
    service = AlertRuleService(db)
    if not await service.delete(rule_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="规则不存在")
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="delete", target_type="alert_rule", target_id=str(rule_id), detail="删除告警规则")
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
    _current_user: User = Depends(require_permission("monitor:view_alerts")),
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
    _current_user: User = Depends(require_permission("monitor:view_alerts")),
):
    service = AlertService(db)
    return await service.get_stats()


@router.put("/{alert_id}/handle")
async def handle_alert(
    alert_id: int,
    req: AlertHandleRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("monitor:handle_alert"))
):
    service = AlertService(db)
    alert = await service.handle(alert_id, req.model_dump(), current_user.username)
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="告警不存在")
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="handle", target_type="alert", target_id=str(alert_id), detail=f"处理告警(状态: {alert.status})")
    return {"message": "处理成功", "status": alert.status}


@router.get("/{alert_id}/attribution")
async def alert_attribution(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_alerts")),
    _llm_rate: None = Depends(user_rate_limit(settings.CHAT_RATE_LIMIT_MAX, settings.CHAT_RATE_LIMIT_WINDOW_SECONDS, "llm")),
):
    """AI 告警归因建议：基于告警信息 + 关联设备 + 实时快照，生成可能原因与处置步骤。"""
    from fastapi import HTTPException
    from app.models.alert import Alert
    from app.models.device import Device

    alert = (await db.execute(select(Alert).where(Alert.id == alert_id))).scalar_one_or_none()
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")

    device_info = ""
    if alert.device_id:
        dev = (await db.execute(select(Device).where(Device.id == alert.device_id))).scalar_one_or_none()
        if dev:
            device_info = (
                "关联设备: 名称={0}, 资产编号={1}, ".format(dev.name, dev.asset_number)
                + "品牌={0}, 型号={1}, ".format(dev.brand or "-", dev.model or "-")
                + "状态={0}, 管理IP={1}".format(dev.status, dev.management_ip or "-")
            )

    snapshot_text = ""
    try:
        snapshot = await get_cached_snapshot()
        service = AssistantService.__new__(AssistantService)
        service.db = None
        snapshot_text = service.build_context_text(snapshot)
    except Exception:
        snapshot_text = ""

    level_label = {"general": "一般", "serious": "严重", "emergency": "紧急"}.get(alert.level, alert.level)
    prompt = (
        "你是数据中心运维告警排查专家。请基于以下告警信息、关联设备与系统实时快照，"
        "给出简洁可行的归因建议。\n"
        "要求：\n"
        "1. 列出2~3条最可能的根因；\n"
        "2. 给出对应的处置步骤（按顺序，可操作）；\n"
        "3. 若数据不足请明确说明；\n"
        "4. 回复控制在200字以内，用中文，条目清晰。\n\n"
        "【告警标题】{0}\n".format(alert.title or "-")
        + "【告警级别】{0}\n".format(level_label)
        + "【告警状态】{0}\n".format(alert.status)
        + "【告警描述】{0}\n".format(alert.description or "-")
        + "【告警对象】类型={0}, ID={1}, 来源={2}\n".format(alert.target_type, alert.target_id, alert.source)
        + device_info + "\n"
    )
    if snapshot_text:
        prompt += "\n【系统实时快照】\n" + snapshot_text[:1500]

    messages = [
        {"role": "system", "content": "你是数据中心运维告警排查专家，输出简洁可操作的中文建议。"},
        {"role": "user", "content": prompt},
    ]
    try:
        suggestion = (await llm_service.chat(messages, temperature=0.2, max_tokens=500)).strip()
    except Exception:
        suggestion = "（AI 服务暂不可用，请结合告警信息与设备状态人工排查。请检查设备连通性、传感器读数与监控阈值配置。）"

    return {"alert_id": alert_id, "suggestion": suggestion}


@router.post("", response_model=AlertResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    req: dict,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("monitor:handle_alert"))
):
    service = AlertService(db)
    obj = await service.create(req)
    # 告警智能收敛：同 dedupe_key 的开放告警归并，叠加 occurrences
    try:
        from app.services.alert_intelligence_service import AlertIntelligenceService
        intel = AlertIntelligenceService(db)
        obj = await intel.converge_new_alert(obj)
    except Exception:
        pass
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="create", target_type="alert", target_id=str(obj.id), detail=f"产生告警: {obj.title}")
    r = AlertResponse.model_validate(obj)
    return r
