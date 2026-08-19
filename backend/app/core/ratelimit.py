# -*- coding: utf-8 -*-
"""简易 IP/用户端口限流器（内存滑动窗口）。

用于登录/注册等无鉴权端点的 IP 限流，以及 AI 聊天等登录端点的按用户限流，
防止暴力碰库、注册垃圾账号，以及 LLM 资源/成本滥用。
注意：内存为单进程状态，多 worker 部署时需 Redis 等外部存储。
"""
import asyncio
import time
from collections import defaultdict, deque

from fastapi import Depends, HTTPException, Request, status


class SlidingWindowLimiter:
    """基于双端队列的滑动窗口限流。"""

    def __init__(self):
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._last_cleanup = time.monotonic()

    async def allow(self, key: str, max_attempts: int, window_seconds: float) -> bool:
        now = time.monotonic()
        async with self._lock:
            q = self._hits[key]
            # 移出超出窗口的时间戳
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= max_attempts:
                return False
            q.append(now)
            # 概率性清理已空的 key，避免内存增长
            if now - self._last_cleanup > 60 and (len(self._hits) > 512):
                self._cleanup(now)
                self._last_cleanup = now
            return True

    def _cleanup(self, now: float):
        expired = [k for k, q in self._hits.items() if not q or now - q[-1] > 120]
        for k in expired:
            del self._hits[k]


# 全局单例




class RedisSlidingWindowLimiter:
    """基于 Redis ZSET 的滑动窗口限流（多 worker 共享计数）。

    仅在配置 REDIS_URL 且 redis 库可用时启用；否则回退进程内内存实现。
    """

    def __init__(self, redis_url: str):
        import redis.asyncio as aioredis
        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._available = True

    async def allow(self, key: str, max_attempts: int, window_seconds: float) -> bool:
        import time
        try:
            now = time.time()
            pipe = self._redis.pipeline()
            pipe.zremrangebyscore(key, 0, now - window_seconds)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, int(window_seconds) + 1)
            results = await pipe.execute()
            count = results[1] + 1
            return count <= max_attempts
        except Exception:
            # Redis 故障时放行（保可用性）；计数可靠性由内存兜底降级交由上层选择
            return True

    async def close(self):
        try:
            await self._redis.aclose()
        except Exception:
            pass


def build_limiter():
    """根据配置构建限流器：优先 Redis（多 worker 集中），否则内存实现。"""
    from app.core.config import settings
    if settings.REDIS_URL:
        try:
            return RedisSlidingWindowLimiter(settings.REDIS_URL)
        except Exception as e:
            import logging
            logging.getLogger("app").warning("Redis 限流初始化失败，回退内存限流: %s", e)
    return SlidingWindowLimiter()

limiter = build_limiter()


def get_client_ip(request: Request) -> str:
    """统一取客户端 IP（委托 app.core.iputils）。"""
    from app.core.iputils import get_client_ip as _resolve
    return _resolve(
        request.headers.get("X-Forwarded-For"),
        request.headers.get("X-Real-IP"),
        request.client.host if request.client else None,
    )


def rate_limit(max_attempts: int, window_seconds: float, scope: str):
    """基于 IP 的限流依赖，超限时返回 429。"""
    async def check(request: Request):
        key = f"{scope}:{get_client_ip(request)}"
        allowed = await limiter.allow(key, max_attempts, window_seconds)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="请求太频繁，请稍后重试",
            )
    return check


def user_rate_limit(max_attempts: int, window_seconds: float, scope: str):
    """基于当前登录用户的限流依赖（防 LLM/写接口资源滥用）。"""
    from app.core.deps import get_current_user

    async def check(current_user=Depends(get_current_user)):
        uid = getattr(current_user, "id", None) or "anon"
        key = f"{scope}:user:{uid}"
        allowed = await limiter.allow(key, max_attempts, window_seconds)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="操作过于频繁，请稍后重试",
            )
    return check