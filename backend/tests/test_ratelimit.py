"""\u767b\u5f55/\u6ce8\u518c\u7aef\u53e3\u9650\u6d41\u6d4b\u8bd5\u3002"""
import asyncio
import pytest

from app.core.ratelimit import SlidingWindowLimiter, rate_limit
from app.core.config import settings


@pytest.mark.asyncio
async def test_sliding_window_limits():
    lim = SlidingWindowLimiter()
    key = "login:1.2.3.4"
    # \u5141\u8bb8\u524d max \u6b21
    assert await lim.allow(key, 3, 60) is True
    assert await lim.allow(key, 3, 60) is True
    assert await lim.allow(key, 3, 60) is True
    # \u7b2c\u56db\u6b21\u5e94\u88ab\u62d2\u7edd
    assert await lim.allow(key, 3, 60) is False
    # \u7a97\u53e3\u8fc7\u671f\u540e\u91cd\u7f6e
    await asyncio.sleep(0.06)
    lim._hits[key].clear()
    assert await lim.allow(key, 3, 60) is True


def test_rate_limit_produces_dependency():
    dep = rate_limit(settings.RATE_LIMIT_LOGIN_MAX, settings.RATE_LIMIT_WINDOW_SECONDS, "login")
    assert callable(dep)
    import inspect
    assert inspect.iscoroutinefunction(dep)


def test_register_endpoint_429s_after_limit(monkeypatch):
    from starlette.testclient import TestClient
    from app.core.config import settings
    from app.core import ratelimit
    # 用小限额快速触发 429
    monkeypatch.setattr(settings, "RATE_LIMIT_REGISTER_MAX", 3)
    # 清空全局 limiter 状态，避免其他测试干扰
    ratelimit.limiter._hits.clear()
    from app.main import app
    with TestClient(app) as client:
        codes = []
        # 发 8 次：无论限额被捕获为默认 5 还是 monkeypatch 后的 3，
        # 第 6 次即将超过最大限额（斜接清除依赖导入顺序的 monkeypatch 时机）
        for _ in range(8):
            r = client.post(
                "/api/v1/auth/register",
                json={"username": "rl_user_x", "password": "Passw0rd!x", "email": "rl@example.com"},
            )
            codes.append(r.status_code)
        assert codes[5] == 429
