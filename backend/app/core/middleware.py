"""全局并发请求限流中间件。

当并发请求超过设定上限时，新请求在限定时间内等待空闲位置，
超时后迅速返回 503，而不是无限排队导致“点快了加载不出来”。
"""
import asyncio
import json

from app.core.concurrency import http_semaphore


class ConcurrencyLimitMiddleware:
    """对所有请求进行并发限流的纯 ASGI 中间件。"""

    def __init__(self, app, timeout: float = 2.0, semaphore=None):
        self.app = app
        self.timeout = timeout
        # 允许测试推入自定义小信号量，不传则用全局 HTTP 信号量。
        self._semaphore = semaphore

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        sem = self._semaphore if self._semaphore is not None else http_semaphore()
        try:
            try:
                await asyncio.wait_for(sem.acquire(), timeout=self.timeout)
            except asyncio.TimeoutError:
                await self._send_503(scope, send)
                return
        except RuntimeError:
            await self.app(scope, receive, send)
            return

        try:
            await self.app(scope, receive, send)
        finally:
            try:
                sem.release()
            except (RuntimeError, ValueError):
                pass

    async def _send_503(self, scope, send):
        body = json.dumps({"detail": "服务忙，请稍后重试"}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 503,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
