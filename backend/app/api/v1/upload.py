"""文件上传与访问API路由"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status, Request
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.file_service import file_service
import logging

logger = logging.getLogger("managesys.upload")

router = APIRouter(prefix="/files", tags=["文件管理"])


@router.post("/upload")
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    sub_dir: str = Query("", description="子目录分类"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传文件（通用，仅超级管理员可用，防止任意登录用户耗尽服务器磁盘）"""
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    try:
        file_info = await file_service.save_upload(file, sub_dir)
        from app.services.audit_service import AuditService
        AuditService.log_request(db, request, current_user=current_user, action="upload", target_type="file", detail=f"上传文件: {file_info.get('filename', file.filename)}")
        return {"message": "上传成功", "data": file_info}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/avatar")
async def upload_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传头像"""
    try:
        result = await file_service.save_avatar(file, current_user.id)
        from app.services.audit_service import AuditService
        AuditService.log_request(db, request, current_user=current_user, action="upload", target_type="file", detail="上传头像")
        return {"message": "头像上传成功", "data": result}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/avatars/{filename}")
async def get_avatar(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    """获取头像文件"""
    file_path = file_service.get_file_path(f"avatars/{filename}")
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="头像不存在")
    return FileResponse(str(file_path))


@router.get("/download/{year}/{month}/{filename}")
async def download_file(
    year: str,
    month: str,
    filename: str,
    sub_dir: str = Query("", description="子目录"),
    current_user: User = Depends(get_current_user),
):
    """下载文件"""
    relative_path = f"{sub_dir}/{year}/{month}/{filename}" if sub_dir else f"{year}/{month}/{filename}"
    file_path = file_service.get_file_path(relative_path)
    if not file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    return FileResponse(
        str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@router.delete("/delete")
async def delete_file(
    request: Request,
    path: str = Query(..., description="文件相对路径"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除文件"""
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    success = file_service.delete_file(path)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="delete", target_type="file", detail=f"删除文件: {path}")
    return {"message": "文件已删除"}
