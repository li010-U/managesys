"""审计日志API路由"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission
from app.models.user import User
from app.schemas.audit_log import AuditLogResponse, AuditLogPageResponse
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["审计日志"])


@router.get("", response_model=AuditLogPageResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    action: Optional[str] = Query(None, description="操作类型: login/logout/create/update/delete/export"),
    target_type: Optional[str] = Query(None, description="对象类型: user/role/device/room/rack/system/alert"),
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("audit:view")),
):
    """获取审计日志列表（分页+多条件筛选）"""
    service = AuditService(db)
    logs, total = await service.get_audit_logs(
        page=page,
        page_size=page_size,
        keyword=keyword,
        action=action,
        target_type=target_type,
        start_date=start_date,
        end_date=end_date,
    )
    return AuditLogPageResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("audit:view")),
):
    """获取审计日志详情"""
    service = AuditService(db)
    log = await service.get_audit_log_by_id(log_id)
    if not log:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="审计日志不存在")
    return AuditLogResponse.model_validate(log)
