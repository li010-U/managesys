"""认证API路由"""
import base64
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.schemas.auth import (
    LoginRequest, TokenResponse, RegisterRequest,
    PasswordChangeRequest, CaptchaResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.services.captcha_service import generate_captcha, verify_captcha

router = APIRouter(prefix="/auth", tags=["认证管理"])


@router.get("/captcha", response_model=CaptchaResponse)
async def get_captcha():
    """获取验证码"""
    if not settings.ENABLE_CAPTCHA:
        return CaptchaResponse(captcha_id="disabled", captcha_image="")
    captcha_id, code, img_bytes = generate_captcha()
    img_base64 = base64.b64encode(img_bytes).decode("utf-8")
    return CaptchaResponse(captcha_id=captcha_id, captcha_image=f"data:image/png;base64,{img_base64}")


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """用户登录"""
    # 验证码校验
    if settings.ENABLE_CAPTCHA:
        if not req.captcha_id or not req.captcha_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入验证码")
        if not verify_captcha(req.captcha_id, req.captcha_code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误")

    service = AuthService(db)
    try:
        ip_address = request.client.host if request.client else None
        token, user = await service.login(req.username, req.password, ip_address)
        return TokenResponse(access_token=token, token_type="bearer")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/register", response_model=UserResponse)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """用户注册"""
    service = AuthService(db)
    try:
        user = await service.register(req)
        return UserResponse.model_validate(user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/change-password")
async def change_password(
    req: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改密码"""
    service = AuthService(db)
    try:
        await service.change_password(current_user.id, req.old_password, req.new_password)
        return {"message": "密码修改成功"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户信息"""
    from sqlalchemy.orm import selectinload
    from app.models.role import Role
    # 重新查询，预加载角色和权限
    result = await db.execute(
        select(User).where(User.id == current_user.id).options(
            selectinload(User.roles).selectinload(Role.permissions)
        )
    )
    fresh_user = result.scalar_one_or_none()
    if not fresh_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user_resp = UserResponse.model_validate(fresh_user)
    for i, role in enumerate(fresh_user.roles):
        user_resp.roles[i].permission_codes = [p.code for p in (role.permissions or [])]
    return user_resp


@router.get("/login-logs")
async def get_login_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取登录日志（仅超级管理员）"""
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
    from sqlalchemy import select, desc
    from app.models.login_log import LoginLog
    from app.schemas.auth import LoginLogResponse
    result = await db.execute(
        select(LoginLog).order_by(desc(LoginLog.created_at)).limit(100)
    )
    logs = result.scalars().all()
    return [LoginLogResponse.model_validate(log) for log in logs]
