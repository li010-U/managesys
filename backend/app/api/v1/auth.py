"""认证API路由"""
import base64
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_current_user
from app.core.ratelimit import rate_limit
from app.core.iputils import get_client_ip, classify_ip
from app.models.user import User
from app.schemas.auth import (
    LoginRequest, TokenResponse, RegisterRequest,
    PasswordChangeRequest, CaptchaResponse, RefreshTokenRequest,
)
from app.core.security import decode_access_token, create_access_token, create_refresh_token, is_refresh_token
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.services.captcha_service import generate_captcha_async, verify_captcha_async

router = APIRouter(prefix="/auth", tags=["认证管理"])


@router.get("/captcha", response_model=CaptchaResponse)
async def get_captcha():
    """获取验证码"""
    if not settings.ENABLE_CAPTCHA:
        return CaptchaResponse(captcha_id="disabled", captcha_image="")
    captcha_id, code, img_bytes = await generate_captcha_async()
    img_base64 = base64.b64encode(img_bytes).decode("utf-8")
    return CaptchaResponse(captcha_id=captcha_id, captcha_image=f"data:image/png;base64,{img_base64}")


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _rate: None = Depends(rate_limit(settings.RATE_LIMIT_LOGIN_MAX, settings.RATE_LIMIT_WINDOW_SECONDS, "login"))
):
    """用户登录"""
    # 验证码校验
    if settings.ENABLE_CAPTCHA:
        if not req.captcha_id or not req.captcha_code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入验证码")
        if not await verify_captcha_async(req.captcha_id, req.captcha_code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="验证码错误")

    service = AuthService(db)
    try:
        ip_address = get_client_ip(request.headers.get("X-Forwarded-For"), request.headers.get("X-Real-IP"), request.client.host if request.client else None)
        token, refresh_token, user = await service.login(
            req.username,
            req.password,
            ip_address,
            request_path=request.url.path[:256],
            user_agent=(request.headers.get("User-Agent") or "")[:512],
        )
        return TokenResponse(
            access_token=token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))


@router.post("/register", response_model=UserResponse)
async def register(
    req: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _rate: None = Depends(rate_limit(settings.RATE_LIMIT_REGISTER_MAX, settings.RATE_LIMIT_WINDOW_SECONDS, "register"))
):
    """用户注册"""
    if not settings.REGISTER_ENABLED:
        from fastapi import status as _status
        raise HTTPException(status_code=_status.HTTP_403_FORBIDDEN, detail="注册功能已关闭，请联系管理员创建账号")

    from app.services.audit_service import AuditService
    service = AuthService(db)
    try:
        user = await service.register(req)
        # 注册审计（由 service.register 内部已写入一条 create 审计，这里无需重复；
        # 若需更完整 request 信息可在此补充，但避免重复，暂不额外写。）
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

@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """退出登录（登出即失效：递增 token_version 使已签发 JWT 立即作废）"""
    from app.services.audit_service import AuditService
    # 跨进程共享数据库层作废：递增 token_version，使已签发的旧 token 立即失效。
    current_user.token_version = (current_user.token_version or 0) + 1
    AuditService.log_request(
        db,
        request,
        current_user=current_user,
        action="logout",
        target_type="auth",
        detail=f"用户 {current_user.username} 退出登录",
    )
    return {"message": "已退出登录"}


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    req: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
    _rate: None = Depends(rate_limit(settings.RATE_LIMIT_LOGIN_MAX, settings.RATE_LIMIT_WINDOW_SECONDS, "refresh")),
):
    """使用刷新令牌换取新的访问令牌（短寿命 JWT 自动续期）。"""
    payload = decode_access_token(req.refresh_token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌无效或已过期")
    if not is_refresh_token(payload):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌类型不正确")
    uid = payload.get("sub")
    try:
        user_id = int(uid)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌无效")
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已停用")
    # 令牌版本校验：改密/登出后 token_version 递增，旧刷新令牌立即失效
    if payload.get("ver") != (user.token_version or 0):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录")
    new_access = create_access_token(
        data={"sub": str(user.id)},
        token_version=user.token_version or 0,
    )
    new_refresh = create_refresh_token(
        data={"sub": str(user.id)},
        token_version=user.token_version or 0,
    )
    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )



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


def _detect_brute_force_ips(records, threshold: int = 5, window_seconds: int = 300) -> set[str]:
    """疑似爆破：同一 IP 在短时间窗口内连续多次登录失败。
    仅针对失败记录计算，返回命中爆破的 IP 集合。
    """
    from datetime import timedelta
    from collections import defaultdict
    window = timedelta(seconds=window_seconds)
    fails_by_ip: dict[str, list] = defaultdict(list)
    for rec in records:
        if getattr(rec, "login_status", None) == "fail" and getattr(rec, "ip_address", None):
            fails_by_ip[rec.ip_address].append(rec.created_at)
    burst_ips: set[str] = set()
    for ip, times in fails_by_ip.items():
        times = sorted(times)
        left = 0
        for right in range(len(times)):
            while times[right] - times[left] > window:
                left += 1
            if right - left + 1 >= threshold:
                burst_ips.add(ip)
                break
    return burst_ips


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
    from collections import defaultdict
    result = await db.execute(
        select(LoginLog).order_by(desc(LoginLog.created_at)).limit(200)
    )
    logs = result.scalars().all()

    # 疑似爆破：同一 IP 短时间窗口内连续失败才打标，成功登录不误判
    burst_ips = _detect_brute_force_ips(logs, threshold=5, window_seconds=300)

    responses = []
    for log in logs:
        resp = LoginLogResponse.model_validate(log)
        flags: list[str] = []
        if log.login_status == "fail" and log.ip_address in burst_ips:
            flags.append("疑似爆破")
        if log.login_status == "success":
            cls = classify_ip(log.ip_address)
            if cls["is_public"]:
                flags.append("公网登录")
        resp.anomaly = flags or None
        responses.append(resp)
    return responses
