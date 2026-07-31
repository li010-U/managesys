"""业务系统管理 API 路由"""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.business_system import BusinessSystem, DeploymentRelation
from app.schemas.business import (
    BusinessSystemCreate, BusinessSystemUpdate, BusinessSystemResponse, BusinessSystemPageResponse,
    DeploymentCreate, DeploymentResponse,
)

router = APIRouter(prefix="/systems", tags=["业务系统管理"])


@router.get("", response_model=BusinessSystemPageResponse)
async def list_systems(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str = Query(None),
    category: str = Query(None),
    bs_status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    q = select(BusinessSystem)
    if keyword:
        q = q.where(or_(BusinessSystem.name.ilike(f"%{keyword}%"), BusinessSystem.code.ilike(f"%{keyword}%")))
    if category:
        q = q.where(BusinessSystem.category == category)
    if bs_status:
        q = q.where(BusinessSystem.status == bs_status)
    q = q.order_by(desc(BusinessSystem.created_at))
    total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
    q = q.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(q)).scalars().all()
    resp = []
    for item in items:
        r = BusinessSystemResponse.model_validate(item)
        r.device_count = len(item.deployments) if item.deployments else 0
        r.doc_count = len(item.documents) if item.documents else 0
        resp.append(r)
    return BusinessSystemPageResponse(items=resp, total=total, page=page, page_size=page_size)


@router.get("/{sys_id}", response_model=BusinessSystemResponse)
async def get_system(sys_id: int, db: AsyncSession = Depends(get_db), _current_user: User = Depends(get_current_user)):
    result = await db.execute(select(BusinessSystem).where(BusinessSystem.id == sys_id))
    item = result.scalar_one_or_none()
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="系统不存在")
    r = BusinessSystemResponse.model_validate(item)
    r.device_count = len(item.deployments) if item.deployments else 0
    r.doc_count = len(item.documents) if item.documents else 0
    return r


@router.post("", response_model=BusinessSystemResponse, status_code=status.HTTP_201_CREATED)
async def create_system(req: BusinessSystemCreate, db: AsyncSession = Depends(get_db), _current_user: User = Depends(get_current_user)):
    try:
        obj = BusinessSystem(**req.model_dump())
        db.add(obj)
        await db.commit()
        await db.refresh(obj)
        return BusinessSystemResponse.model_validate(obj)
    except Exception as e:
        from fastapi import HTTPException
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.put("/{sys_id}", response_model=BusinessSystemResponse)
async def update_system(sys_id: int, req: BusinessSystemUpdate, db: AsyncSession = Depends(get_db), _current_user: User = Depends(get_current_user)):
    result = await db.execute(select(BusinessSystem).where(BusinessSystem.id == sys_id))
    obj = result.scalar_one_or_none()
    if not obj:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="系统不存在")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    await db.commit()
    await db.refresh(obj)
    r = BusinessSystemResponse.model_validate(obj)
    r.device_count = len(obj.deployments) if obj.deployments else 0
    r.doc_count = len(obj.documents) if obj.documents else 0
    return r


@router.delete("/{sys_id}")
async def delete_system(sys_id: int, db: AsyncSession = Depends(get_db), _current_user: User = Depends(get_current_user)):
    result = await db.execute(select(BusinessSystem).where(BusinessSystem.id == sys_id))
    obj = result.scalar_one_or_none()
    if not obj:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="系统不存在")
    await db.delete(obj)
    await db.commit()
    return {"message": "系统已删除"}


@router.get("/{sys_id}/deployments")
async def list_deployments(sys_id: int, db: AsyncSession = Depends(get_db), _current_user: User = Depends(get_current_user)):
    result = await db.execute(select(DeploymentRelation).where(DeploymentRelation.system_id == sys_id))
    items = result.scalars().all()
    resp = []
    for item in items:
        r = DeploymentResponse.model_validate(item)
        if item.device:
            r.device_name = item.device.name
        resp.append(r)
    return resp


@router.post("/{sys_id}/deployments", response_model=DeploymentResponse, status_code=status.HTTP_201_CREATED)
async def create_deployment(sys_id: int, req: DeploymentCreate, db: AsyncSession = Depends(get_db), _current_user: User = Depends(get_current_user)):
    data = req.model_dump()
    data["system_id"] = sys_id
    obj = DeploymentRelation(**data)
    db.add(obj)
    await db.commit()
    await db.refresh(obj)
    r = DeploymentResponse.model_validate(obj)
    if obj.device:
        r.device_name = obj.device.name
    return r


@router.delete("/{sys_id}/deployments/{dep_id}")
async def delete_deployment(sys_id: int, dep_id: int, db: AsyncSession = Depends(get_db), _current_user: User = Depends(get_current_user)):
    result = await db.execute(select(DeploymentRelation).where(DeploymentRelation.id == dep_id, DeploymentRelation.system_id == sys_id))
    obj = result.scalar_one_or_none()
    if not obj:
        from fastapi import HTTPException
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="关联不存在")
    await db.delete(obj)
    await db.commit()
    return {"message": "关联已删除"}
