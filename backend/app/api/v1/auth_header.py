"""认证API路由"""
import logging
import base64
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.role import Role
from app.schemas.auth import (
    LoginRequest, TokenResponse, RegisterRequest,
    PasswordChangeRequest, CaptchaResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService
from app.services.captcha_service import (
    generate_captcha_db, 
    verify_captcha_db,
    generate_captcha,
    verify_captcha,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["认证"])

