# -*- coding: utf-8 -*-
"""Request-ID 追踪：为每条请求生成唯一标识并贯穿日志。

- 从请求头 X-Request-ID 读取；缺失或超长时按 UUID 生成
- 通过 contextvars 在整个请求链路内透传 req_id
- 响应头回写 X-Request-ID，便于端到端排障
"""
import logging
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from contextvars import ContextVar, Token

# 每条请求从 contextvars 取 req_id，默认 "-"
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


def current_request_id() -> str:
    """获取当前请求的 request-id，供日志 Filter 使用。"""
    return request_id_var.get()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """读取请求头 X-Request-ID，写入 contextvars，响应头回写。"""

    def __init__(self, app):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID", "").strip()
        if not rid or len(rid) > 64:
            rid = uuid.uuid4().hex
        token: Token = request_id_var.set(rid)
        try:
            response: Response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers.setdefault("X-Request-ID", rid)
        return response


class RequestIDFilter(logging.Filter):
    """从 contextvars 取 request-id 写入日志记录。"""

    def filter(self, record: logging.LogRecord) -> bool:
        record.req_id = current_request_id()
        return True
