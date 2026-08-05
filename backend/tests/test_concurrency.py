"""并发控制组件测试：
- 全局 SSE 信号量限制并发连接。
- ConcurrencyLimitMiddleware 在并发超限时返回 503 而不是无限排队。
"""
import asyncio

import pytest

from app.core.concurrency import sse_semaphore, http_semaphore


@pytest.mark.asyncio
async def test_sse_semaphore_limits_concurrent():
    sem = sse_semaphore()
    acquired = []
    for _ in range(sem._value):
        acquired.append(await sem.acquire())
    try:
        await asyncio.wait_for(sem.acquire(), timeout=0.1)
        blocked = False
    except asyncio.TimeoutError:
        blocked = True
    assert blocked
    for a in acquired:
        sem.release()


@pytest.mark.asyncio
async def test_http_semaphore_returns_same_semaphore():
    assert http_semaphore() is http_semaphore()


def test_concurrency_middleware_returns_503_when_full():
    from app.core.middleware import ConcurrencyLimitMiddleware

    sent = []
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "http_version": "1.1",
        "client": ("test", 1),
        "server": ("test", 8000),
        "scheme": "http",
        "root_path": "",
        "state": {},
    }

    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": [], "detach": True})

    async def _append_send(message):
        sent.append(message)

    async def run():
        # 信号量 0 许可：等待超时后迅速 503
        mw = ConcurrencyLimitMiddleware(downstream, timeout=0.1, semaphore=asyncio.Semaphore(0))
        await mw(scope, lambda: None, _append_send)

    asyncio.run(run())
    start = next((m for m in sent if m["type"] == "http.response.start"), None)
    assert start is not None
    assert start["status"] == 503


def test_concurrency_middleware_passes_through_when_free():
    from app.core.middleware import ConcurrencyLimitMiddleware

    sent = []
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "http_version": "1.1",
        "client": ("test", 1),
        "server": ("test", 8000),
        "scheme": "http",
        "root_path": "",
        "state": {},
    }

    async def downstream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": [], "detach": True})

    async def _append_send2(message):
        sent.append(message)

    async def run():
        # 许可充足：放行给下游
        mw = ConcurrencyLimitMiddleware(downstream, timeout=0.1, semaphore=asyncio.Semaphore(5))
        await mw(scope, lambda: None, _append_send2)

    asyncio.run(run())
    start = next((m for m in sent if m["type"] == "http.response.start"), None)
    assert start is not None
    assert start["status"] == 200



# ===== exec_sql query timeout =====

@pytest.mark.asyncio
async def test_exec_sql_times_out_on_slow_query(monkeypatch):
    import asyncio
    from app.db.compat_sql import exec_sql
    from app.core.config import settings

    # \u77ed\u8d85\u65f6\uff0c\u907f\u514d\u6d4b\u8bd5\u7b49\u5f85\u8fc7\u4e45
    monkeypatch.setattr(settings, "DB_QUERY_TIMEOUT", 0.05)

    class SlowSession:
        async def execute(self, *a, **k):
            await asyncio.sleep(1.0)
            return "unused"

    with pytest.raises(asyncio.TimeoutError):
        await exec_sql(SlowSession(), "SELECT 1")

@pytest.mark.asyncio
async def test_exec_sql_returns_on_fast_query(monkeypatch):
    from app.db.compat_sql import exec_sql
    from app.core.config import settings
    import asyncio

    monkeypatch.setattr(settings, "DB_QUERY_TIMEOUT", 5)

    class FastSession:
        async def execute(self, *a, **k):
            return "row", "row"

    assert (await exec_sql(FastSession(), "SELECT 1")) == ("row", "row")
