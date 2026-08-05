"""角色与权限API路由"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission
from app.models.user import User
from app.schemas.role import RoleResponse, RoleCreateRequest, RoleUpdateRequest, PermissionInfo
from app.services.role_service import RoleService
from app.services.permission_service import PermissionService

router = APIRouter(prefix="/roles", tags=["角色管理"])


def get_client_ip(request: Request) -> str:
    """获取客户端真实IP"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.get("", response_model=list[RoleResponse])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:view")),
):
    """获取所有角色"""
    service = RoleService(db)
    roles = await service.get_roles()
    return [RoleResponse.model_validate(r) for r in roles]


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:view")),
):
    """获取角色详情"""
    service = RoleService(db)
    role = await service.get_role_by_id(role_id)
    if not role:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
    return RoleResponse.model_validate(role)


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    req: RoleCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """创建角色"""
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    service = RoleService(db)
    try:
        role = await service.create_role(
            req,
            operator_username=current_user.username,
            operator_ip=get_client_ip(request),
        )
        return RoleResponse.model_validate(role)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: int,
    req: RoleUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新角色"""
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    service = RoleService(db)
    try:
        role = await service.update_role(
            role_id, req,
            operator_username=current_user.username,
            operator_ip=get_client_ip(request),
        )
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
        return RoleResponse.model_validate(role)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{role_id}")
async def delete_role(
    role_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除角色"""
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    service = RoleService(db)
    try:
        result = await service.delete_role(
            role_id,
            operator_username=current_user.username,
            operator_ip=get_client_ip(request),
        )
        if not result:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="角色不存在")
        return {"message": "角色已删除"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/permissions/list", response_model=list[PermissionInfo])
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("role:view")),
):
    """获取所有权限列表"""
    service = PermissionService(db)
    perms = await service.get_permissions()
    return [PermissionInfo.model_validate(p) for p in perms]
