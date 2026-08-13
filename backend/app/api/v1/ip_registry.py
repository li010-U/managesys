"""IP 地址台账与子网管理 API"""
from typing import Optional
from fastapi import APIRouter, Depends, Request, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission
from app.models.user import User
from app.services.ip_registry_service import IpRegistryService

router = APIRouter(prefix="/ip-registry", tags=["IP资源台账"])


class SubnetCreate(BaseModel):
    name: str = Field(..., max_length=128, description="子网名称")
    network: str = Field(..., max_length=64, description="网段地址")
    prefix: int = Field(8, ge=1, le=32, description="前缀长度")
    gateway: Optional[str] = Field(None, max_length=64)
    vlan: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = Field(None, max_length=256)
    status: str = Field("active", description="active/disabled")


class SubnetUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    gateway: Optional[str] = Field(None, max_length=64)
    vlan: Optional[str] = Field(None, max_length=64)
    description: Optional[str] = Field(None, max_length=256)
    status: Optional[str] = None


class AddressSave(BaseModel):
    address: str = Field(..., max_length=64)
    status: str = Field(..., description="free/reserved/allocated")
    subnet_id: Optional[int] = None
    device_id: Optional[int] = None
    used_as: Optional[str] = Field(None, max_length=16)
    remark: Optional[str] = Field(None, max_length=256)


@router.get("/subnets")
async def list_subnets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("device:view")),
):
    return await IpRegistryService(db).list_subnets()


@router.post("/subnets", status_code=201)
async def create_subnet(
    req: SubnetCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("device:edit")),
):
    svc = IpRegistryService(db)
    try:
        sub = await svc.create_subnet(req.name, req.network, req.prefix, req.gateway, req.vlan, req.description, req.status)
        from app.services.audit_service import AuditService
        AuditService.log_request(db, request, current_user=current_user, action="create", target_type="subnet", target_id=str(sub.id), detail=f"创建子网: {req.network}/{req.prefix}")
        return {"id": sub.id, "cidr": f"{sub.network}/{sub.prefix}"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/subnets/{subnet_id}")
async def update_subnet(
    subnet_id: int,
    req: SubnetUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("device:edit")),
):
    svc = IpRegistryService(db)
    sub = await svc.update_subnet(subnet_id, name=req.name, gateway=req.gateway, vlan=req.vlan, description=req.description, status=req.status)
    if not sub:
        raise HTTPException(status_code=404, detail="子网不存在")
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="update", target_type="subnet", target_id=str(subnet_id), detail="更新子网")
    return {"message": "更新成功"}


@router.delete("/subnets/{subnet_id}")
async def delete_subnet(
    subnet_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("device:delete")),
):
    svc = IpRegistryService(db)
    if not await svc.delete_subnet(subnet_id):
        raise HTTPException(status_code=404, detail="子网不存在")
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="delete", target_type="subnet", target_id=str(subnet_id), detail="删除子网")
    return {"message": "删除成功"}


@router.get("/addresses")
async def list_addresses(
    subnet_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("device:view")),
):
    items, total = await IpRegistryService(db).list_addresses(subnet_id, status, keyword, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/addresses", status_code=201)
async def save_address(
    req: AddressSave,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("device:edit")),
):
    svc = IpRegistryService(db)
    try:
        row = await svc.save_address(req.address, req.status, req.subnet_id, req.device_id, req.used_as, req.remark)
        from app.services.audit_service import AuditService
        AuditService.log_request(db, request, current_user=current_user, action="update", target_type="ip_address", target_id=str(row.id), detail=f"登记IP {req.address} 状态={req.status}")
        return {"id": row.id, "address": row.address, "status": row.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/addresses/{address_id}")
async def delete_address(
    address_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("device:edit")),
):
    svc = IpRegistryService(db)
    if not await svc.delete_address(address_id):
        raise HTTPException(status_code=404, detail="IP不存在")
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="delete", target_type="ip_address", target_id=str(address_id), detail="删除IP台账")
    return {"message": "删除成功"}


@router.post("/import-device-ips")
async def import_device_ips(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("device:edit")),
):
    result = await IpRegistryService(db).import_device_ips()
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="execute", target_type="ip_address", detail="从设备导入IP台账")
    return result
