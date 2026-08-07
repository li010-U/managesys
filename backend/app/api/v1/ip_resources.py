"""IP 资源概览 API。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_permission
from app.models.user import User
from app.services.ip_resource_service import IpResourceService

router = APIRouter(prefix="/ip-resources", tags=["IP资源"])


@router.get("/overview")
async def ip_resource_overview(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("device:view")),
):
    return await IpResourceService(db).overview()
