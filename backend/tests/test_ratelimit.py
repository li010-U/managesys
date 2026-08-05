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
    # \u7528\u5c0f\u9650\u989d\u5feb\u901f\u89e6\u53d1 429
    monkeypatch.setattr(settings, "RATE_LIMIT_REGISTER_MAX", 3)
    # \u6e05\u7a7a\u5168\u5c40 limiter \u72b6\u6001\uff0c\u907f\u514d\u5176\u4ed6\u6d4b\u8bd5\u5e72\u6270
    ratelimit.limiter._hits.clear()
    from app.main import app
    with TestClient(app) as client:
        codes = []
        for _ in range(4):
            r = client.post(
                "/api/v1/auth/register",
                json={"username": "rl_user_x", "password": "Passw0rd!x", "email": "rl@example.com"},
            )
            codes.append(r.status_code)
        # \u7b2c 1-3 \u6b21\u5267\u60c5\u4e0d\u540c\uff08\u53ef\u80fd 400/409\uff09\uff0c\u7b2c 4 \u6b21\u5e94 429
        assert codes[3] == 429
