"""IP 地址台账与子网管理 API"""
from typing import Optional
from datetime import datetime
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
    vlan_id: Optional[int] = Field(None)
    description: Optional[str] = Field(None, max_length=256)
    status: str = Field("active", description="active/disabled")


class SubnetUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    gateway: Optional[str] = Field(None, max_length=64)
    vlan: Optional[str] = Field(None, max_length=64)
    vlan_id: Optional[int] = Field(None)
    description: Optional[str] = Field(None, max_length=256)
    status: Optional[str] = None


class AddressSave(BaseModel):
    address: Optional[str] = Field(None, max_length=64)
    preferred: Optional[str] = Field(None, max_length=64)
    status: str = Field(..., description="free/reserved/allocated")
    subnet_id: Optional[int] = None
    device_id: Optional[int] = None
    used_as: Optional[str] = Field(None, max_length=16)
    remark: Optional[str] = Field(None, max_length=256)


# ===== ?????? =====
class IpAddressItem(BaseModel):
    id: int
    address: str
    status: str
    subnet_id: Optional[int] = None
    subnet: Optional[str] = None
    device_id: Optional[int] = None
    device_name: Optional[str] = None
    used_as: Optional[str] = None
    remark: Optional[str] = None
    updated_at: Optional[datetime] = None


class IpAddressPageResponse(BaseModel):
    items: list[IpAddressItem]
    total: int
    page: int
    page_size: int


class IpHistoryItem(BaseModel):
    id: int
    ip_id: int
    address: str
    field_changed: Optional[str] = None
    from_value: Optional[str] = None
    to_value: Optional[str] = None
    operator: Optional[str] = None
    source: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[datetime] = None


class IpHistoryPageResponse(BaseModel):
    items: list[IpHistoryItem]
    total: int
    page: int
    page_size: int

@router.get("/subnets")
async def list_subnets(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("ip:view")),
):
    return await IpRegistryService(db).list_subnets()


@router.post("/subnets", status_code=201)
async def create_subnet(
    req: SubnetCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("ip:edit")),
):
    svc = IpRegistryService(db)
    try:
        sub = await svc.create_subnet(req.name, req.network, req.prefix, req.gateway, req.vlan, req.vlan_id, req.description, req.status)
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
    current_user: User = Depends(require_permission("ip:edit")),
):
    svc = IpRegistryService(db)
    sub = await svc.update_subnet(subnet_id, name=req.name, gateway=req.gateway, vlan=req.vlan, vlan_id=req.vlan_id, description=req.description, status=req.status)
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
    current_user: User = Depends(require_permission("ip:edit")),
):
    svc = IpRegistryService(db)
    if not await svc.delete_subnet(subnet_id):
        raise HTTPException(status_code=404, detail="子网不存在")
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="delete", target_type="subnet", target_id=str(subnet_id), detail="删除子网")
    return {"message": "删除成功"}


@router.get("/addresses", response_model=IpAddressPageResponse)
async def list_addresses(
    subnet_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("ip:view")),
):
    items, total = await IpRegistryService(db).list_addresses(subnet_id, status, keyword, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/addresses", status_code=201)
async def save_address(
    req: AddressSave,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("ip:allocate")),
):
    svc = IpRegistryService(db)
    try:
        row = await svc.save_address(req.address, req.status, req.subnet_id, req.device_id, req.used_as, req.remark, operator=current_user.username)
        from app.services.audit_service import AuditService
        AuditService.log_request(db, request, current_user=current_user, action="update", target_type="ip_address", target_id=str(row.id), detail=f"登记IP {req.address} 状态={req.status}")
        return {"id": row.id, "address": row.address, "status": row.status}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/allocate", status_code=201)
async def allocate_address(
    req: AddressSave,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("ip:allocate")),
):
    """\u4ece\u6307\u5b9a\u5b50\u7f51\u81ea\u52a8\u5206\u914d\u4e00\u4e2a\u7a7a\u95f2 IP\uff08\u53ef\u4f20 preferred \u4f5c\u4e3a\u504f\u597d\uff09\u3002"""
    svc = IpRegistryService(db)
    try:
        addr = req.preferred or (req.address if req.address else None)
        result = await svc.allocate_ip(req.subnet_id, req.used_as or "management", req.device_id,
                                       operator=current_user.username, preferred=addr)
        from app.services.audit_service import AuditService
        AuditService.log_request(db, request, current_user=current_user, action="execute", target_type="ip_address", target_id=str(result["id"]), detail="\u81ea\u52a8\u5206\u914d IP " + result["address"])
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history", response_model=IpHistoryPageResponse)
async def list_history(
    address: Optional[str] = Query(None),
    address_id: Optional[int] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("ip:view")),
):
    """\u67e5\u8be2 IP \u53f0\u8d26\u53d8\u66f4\u5386\u53f2\u3002"""
    items, total = await IpRegistryService(db).list_history(address, address_id, page, page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.delete("/addresses/{address_id}")
async def delete_address(
    address_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("ip:edit")),
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
    current_user: User = Depends(require_permission("ip:edit")),
):
    result = await IpRegistryService(db).import_device_ips()
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="execute", target_type="ip_address", detail="从设备导入IP台账")
    return result

# ==================== VLAN 管理 ====================

@router.get("/vlans")
async def list_vlans(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("ip:view")),
):
    return await IpRegistryService(db).list_vlans()


class VlanCreate(BaseModel):
    vlan_id: int = Field(..., description="\u0056LAN \u7f16\u53f7")
    name: str = Field("", max_length=128)
    description: Optional[str] = Field(None, max_length=256)
    room_id: Optional[int] = None
    status: str = Field("active")


class VlanUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    description: Optional[str] = Field(None, max_length=256)
    room_id: Optional[int] = None
    status: Optional[str] = None


@router.post("/vlans", status_code=201)
async def create_vlan(
    req: VlanCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("ip:edit")),
):
    try:
        v = await IpRegistryService(db).create_vlan(req.vlan_id, req.name, req.description, req.room_id, req.status)
        from app.services.audit_service import AuditService
        AuditService.log_request(db, request, current_user=current_user, action="create", target_type="vlan", target_id=str(v.id), detail="\u521b\u5efa VLAN " + str(req.vlan_id))
        return {"id": v.id, "vlan_id": v.vlan_id, "name": v.name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/vlans/{vlan_pk}")
async def update_vlan(
    vlan_pk: int,
    req: VlanUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("ip:edit")),
):
    v = await IpRegistryService(db).update_vlan(vlan_pk, req.name, req.description, req.room_id, req.status)
    if not v:
        raise HTTPException(status_code=404, detail="\u0056LAN \u4e0d\u5b58\u5728")
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="update", target_type="vlan", target_id=str(vlan_pk), detail="\u66f4\u65b0 VLAN " + str(v.vlan_id))
    return {"message": "\u66f4\u65b0\u6210\u529f"}


@router.delete("/vlans/{vlan_pk}")
async def delete_vlan(
    vlan_pk: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("ip:recycle")),
):
    if not await IpRegistryService(db).delete_vlan(vlan_pk):
        raise HTTPException(status_code=404, detail="\u0056LAN \u4e0d\u5b58\u5728")
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="delete", target_type="vlan", target_id=str(vlan_pk), detail="\u5220\u9664 VLAN")
    return {"message": "\u5220\u9664\u6210\u529f"}


# ==================== CSV 导出 ====================

@router.get("/subnets/export")
async def export_subnets(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("ip:view")),
):
    csv_text = await IpRegistryService(db).export_subnets_csv()
    from fastapi.responses import Response
    return Response(content=csv_text, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=subnets.csv"})


@router.get("/addresses/export")
async def export_addresses(
    subnet_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("ip:view")),
):
    csv_text = await IpRegistryService(db).export_addresses_csv(subnet_id, status)
    from fastapi.responses import Response
    return Response(content=csv_text, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=addresses.csv"})


