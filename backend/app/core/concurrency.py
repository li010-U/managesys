"""全局并发控制工具。

主要用于防止“点快了加载不出来”与多人同时在线时的资源恜死：
- HTTP 并发请求限流（超出后迅速返回 503，而非无限排队）。
- SSE 长连接数量限制（同一进程内限制并发 SSE 连接）。
"""
import asyncio
import weakref

from app.core.config import settings


def _make_semaphore(permits: int) -> asyncio.Semaphore:
    """asyncio.Semaphore 会绑定到首个使用它的事件循环，这里按事件循环懒创建，
    避免测试/重载等切换事件循环时报 “bound to a different event loop”。"""
    return asyncio.Semaphore(permits)


# 按事件循环的 HTTP 并发限流信号量
_http_by_loop = weakref.WeakKeyDictionary()
# 按事件循环的 SSE 连接信号量
_sse_by_loop = weakref.WeakKeyDictionary()


def http_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _http_by_loop.get(loop)
    if sem is None:
        sem = _make_semaphore(settings.HTTP_MAX_CONCURRENCY)
        _http_by_loop[loop] = sem
    return sem


def sse_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _sse_by_loop.get(loop)
    if sem is None:
        sem = _make_semaphore(settings.SSE_MAX_CONNECTIONS)
        _sse_by_loop[loop] = sem
    return sem
