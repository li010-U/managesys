"""认证相关 Pydantic Schema"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")
    captcha_id: Optional[str] = Field(None, description="验证码ID")
    captcha_code: Optional[str] = Field(None, min_length=4, max_length=4, description="验证码")


class TokenResponse(BaseModel):
    access_token: str = Field(..., description="JWT访问令牌")
    token_type: str = Field("bearer", description="令牌类型")


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64, description="用户名")
    password: str = Field(..., min_length=8, max_length=128, description="密码")
    real_name: Optional[str] = Field(None, max_length=64, description="真实姓名")
    email: Optional[str] = Field(None, max_length=128, description="邮箱")
    phone: Optional[str] = Field(None, max_length=20, description="手机号")
    department: Optional[str] = Field(None, max_length=128, description="部门")


class PasswordChangeRequest(BaseModel):
    old_password: str = Field(..., description="旧密码")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")


class CaptchaResponse(BaseModel):
    captcha_id: str = Field(..., description="验证码ID")
    captcha_image: str = Field(..., description="验证码图片(base64)")


class LoginLogResponse(BaseModel):
    id: int
    username: str
    ip_address: Optional[str] = None
    login_status: str
    fail_reason: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}
