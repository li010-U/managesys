"""带 TTL 与并发合并的 singleflight 缓存。

特点
- 顽建 TTL 过期后自动重新加载
- 并发请求合并：随机一个加载，其余等待其结果

用于隔离重网络对调用，减少高并发下的重复请求。
"""
import asyncio
import time
import weakref
from typing import Any, Awaitable, Callable, Optional, Tuple


class AsyncTTLSingleFlight:
    """带 TTL 与并发合并的单飞缓存。"""

    def __init__(self, ttl_seconds: float = 4.0, loader_timeout_seconds: float = 0.0):
        self.ttl_seconds = ttl_seconds
        self.loader_timeout_seconds = loader_timeout_seconds
        self._by_loop = weakref.WeakKeyDictionary()

    def _state(self):
        loop = asyncio.get_running_loop()
        st = self._by_loop.get(loop)
        if st is None:
            st = {"value": None, "expire": 0.0, "lock": None, "pending": None,
                  "generation": 0}
            self._by_loop[loop] = st
        return st

    async def get_or_load(self, loader: Callable[[], Awaitable[Any]]) -> Any:
        st = self._state()
        now = time.monotonic()
        # 命中未过期缓存，直接返回
        if st["value"] is not None and now < st["expire"]:
            return st["value"]

        if st["lock"] is None:
            st["lock"] = asyncio.Lock()
        lock = st["lock"]

        async with lock:
            # 双检锁：等待期间可能已被并发填充，二次确认
            if st["value"] is not None and time.monotonic() < st["expire"]:
                return st["value"]
            # Record the generation when this load starts, so a load that was
            # already in flight when invalidate() was called will not resurrect
            # stale data after invalidation.
            gen_at_start = st["generation"]
            if self.loader_timeout_seconds:
                value = await asyncio.wait_for(
                    loader(), timeout=self.loader_timeout_seconds
                )
            else:
                value = await loader()
            # Only persist the freshly loaded value if the cache was not
            # invalidated while we were loading.
            if st["generation"] == gen_at_start:
                st["value"] = value
                st["expire"] = time.monotonic() + self.ttl_seconds
            return value

    def invalidate(self) -> None:
        for st in self._by_loop.values():
            st["value"] = None
            st["expire"] = 0.0
            st["generation"] += 1
