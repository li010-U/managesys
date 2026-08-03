"""统一异常处理和错误响应"""
import logging
from typing import Optional

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    """业务逻辑异常基类"""
    def __init__(self, message: str, code: str = "SERVICE_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class NotFoundError(ServiceError):
    """资源不存在"""
    def __init__(self, resource: str, resource_id: Optional[int] = None):
        msg = f"{resource}不存在"
        if resource_id:
            msg = f"{resource}(ID:{resource_id})不存在"
        super().__init__(msg, "NOT_FOUND")


class ValidationError(ServiceError):
    """数据验证失败"""
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


class PermissionDeniedError(ServiceError):
    """权限不足"""
    def __init__(self, message: str = "权限不足"):
        super().__init__(message, "PERMISSION_DENIED")


class ConflictError(ServiceError):
    """资源冲突（如用户名已存在）"""
    def __init__(self, message: str):
        super().__init__(message, "CONFLICT")


def raise_not_found(resource: str, resource_id: Optional[int] = None):
    """抛出 404 异常"""
    exc = NotFoundError(resource, resource_id)
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)


def raise_validation_error(message: str):
    """抛出 400 验证错误异常"""
    exc = ValidationError(message)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)


def raise_conflict(message: str):
    """抛出 409 冲突异常"""
    exc = ConflictError(message)
    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.message)


def handle_service_error(e: ServiceError, resource: str = None, resource_id: int = None) -> None:
    """处理业务逻辑异常"""
    if isinstance(e, NotFoundError):
        raise_not_found(resource or e.message.split("(")[0].rstrip("不存在"), resource_id)
    elif isinstance(e, ValidationError):
        raise_validation_error(e.message)
    elif isinstance(e, ConflictError):
        raise_conflict(e.message)
    else:
        logger.error(f"服务错误: {e.code} - {e.message}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误"
        )


def safe_handle_error(e: Exception, operation: str, resource: str = None) -> None:
    """安全地处理未知异常，记录日志但不暴露细节"""
    if isinstance(e, ServiceError):
        handle_service_error(e, resource)
    elif isinstance(e, HTTPException):
        raise e
    else:
        logger.error(f"{operation}失败: {type(e).__name__}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误，请稍后重试"
        )
