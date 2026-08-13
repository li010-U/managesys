# -*- coding: utf-8 -*-
"""IP ?? API?"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission, require_any_permission
from app.models.user import User
from app.services.ip_resource_service import IpResourceService

router = APIRouter(prefix="/ip-resources", tags=["IP??"])


class IpResolveRequest(BaseModel):
    device_id: int = Field(..., description="冲突设备 ID")
    role: str = Field(..., description="IP 角色（management/business/oob）")
    new_ip: str = Field(..., max_length=128, description="修改后的新 IP")


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.get("/overview")
async def ip_resource_overview(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    return await IpResourceService(db).overview()


@router.get("/conflicts")
async def ip_resource_conflicts(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    return await IpResourceService(db).conflicts()


@router.post("/resolve")
async def ip_resource_resolve(
    req: IpResolveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_any_permission("device:edit", "device:create")),
):
    try:
        return await IpResourceService(db).resolve_conflict(
            req.device_id, req.role, req.new_ip,
            operator_username=current_user.username,
            operator_ip=get_client_ip(request),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
