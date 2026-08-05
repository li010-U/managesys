"""\u7b80\u6613 IP \u7aef\u53e3\u9650\u6d41\u5668\uff08\u5185\u5b58\u6ed1\u52a8\u7a97\u53e3\uff09\u3002

\u7528\u4e8e\u767b\u5f55 / \u6ce8\u518c\u7b49\u65e0\u9274\u6743\u7aef\u70b9\uff0c\u9632\u6b62\u66b4\u529b\u78b0\u5e93\u4e0e\u5927\u91cf\u6ce8\u518c\u5783\u573e\u8d26\u53f7\u3002
\u6ce8\u610f\uff1a\u5185\u5b58\u4e3a\u5355\u8fdb\u7a0b\u72b6\u6001\uff0c\u591a worker \u90e8\u7f72\u65f6\u9700\u8981 Redis \u7b49\u5916\u90e8\u5b58\u50a8\uff1b
\u5355 worker\uff08SQLite \u9ed8\u8ba4\uff09\u4e0b\u6709\u6548\u3002
"""
import asyncio
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status


class SlidingWindowLimiter:
    """\u57fa\u4e8e\u53cc\u7aef\u961f\u5217\u7684\u6ed1\u52a8\u7a97\u53e3\u9650\u6d41\u3002"""

    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._last_cleanup = time.monotonic()

    async def allow(self, key: str, max_attempts: int, window_seconds: float) -> bool:
        now = time.monotonic()
        async with self._lock:
            q = self._hits[key]
            # \u79fb\u9664\u8d85\u51fa\u7a97\u53e3\u7684\u65f6\u95f4\u6233
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= max_attempts:
                return False
            q.append(now)
            # \u6982\u7387\u6027\u6e05\u7406\u5df2\u7a7a\u7684 key\uff0c\u907f\u514d\u5185\u5b58\u589e\u957f
            if now - self._last_cleanup > 60:
                self._cleanup(now)
                self._last_cleanup = now
            return True

    def _cleanup(self, now: float):
        expired = [k for k, q in self._hits.items() if not q or now - q[-1] > 120]
        for k in expired:
            del self._hits[k]


# \u5168\u5c40\u5355\u4f8b
limiter = SlidingWindowLimiter()


def get_client_ip(request: Request) -> str:
    """\u4f18\u5148\u53d6 X-Forwarded-For \u7684\u7b2c\u4e00\u4e2a IP\uff0c\u540e\u56de\u9000\u5230\u8fde\u63a5\u5bf9\u7aef\u5730\u5740\u3002"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def rate_limit(max_attempts: int, window_seconds: float, scope: str):
    """\u751f\u6210\u4e00\u4e2a\u9650\u6d41\u4f9d\u8d56\uff0c\u8d85\u9650\u65f6\u8fd4\u56de 429\u3002"""
    async def check(request: Request):
        key = f"{scope}:{get_client_ip(request)}"
        allowed = await limiter.allow(key, max_attempts, window_seconds)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="\u8bf7\u6c42\u592a\u9891\u7e41\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5",
            )
    return check
