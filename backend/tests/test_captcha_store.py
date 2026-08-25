# -*- coding: utf-8 -*-
"""验证码存储后端（内存 / Redis）回归测试。

验证两个关键性质：
1. 一次性消费（atomic single-use）：同一 captcha_id 只有一次能校验成功。
2. 多 worker 场景可共享存储（Redis 后端），且 Redis 故障时回退内存（fail-open）。
"""
import sys
import types
from unittest.mock import patch

import pytest


@pytest.mark.asyncio
async def test_memory_store_generate_and_atomic_consume():
    from app.services.captcha_service import MemoryCaptchaStore

    store = MemoryCaptchaStore()
    captcha_id, code = await store.generate()

    assert len(captcha_id) > 0
    assert len(code) == 6

    # 第一次消费成功
    first = await store.consume(captcha_id)
    assert first == code
    # 第二次消费（重复提交同一次验证码）返回 None => 只有一次成功
    second = await store.consume(captcha_id)
    assert second is None


@pytest.mark.asyncio
async def test_default_store_is_memory_when_no_redis():
    """未配置 REDIS_URL 时，默认应为内存存储（单 worker 零成本）。"""
    from app.core.config import settings
    from app.services.captcha_service import (
        MemoryCaptchaStore, get_captcha_store, reset_captcha_store_for_tests,
    )

    reset_captcha_store_for_tests()
    try:
        with patch.object(settings, "REDIS_URL", ""):
            store = get_captcha_store()
        assert isinstance(store, MemoryCaptchaStore)
    finally:
        reset_captcha_store_for_tests()


class _FakeRedis:
    """最小化的 Redis 客户端替身，用于验证 RedisCaptchaStore 逻辑。"""

    def __init__(self):
        self.data = {}
        self.fail = False

    async def set(self, key, value, ex=None):
        if self.fail:
            raise ConnectionError("redis down")
        self.data[key] = value
        return True

    async def getdel(self, key):
        if self.fail:
            raise ConnectionError("redis down")
        return self.data.pop(key, None)

    async def aclose(self):
        return None


async def _install_fake_redis(fake):
    """把假 redis.asyncio 模块注入 sys.modules，供 RedisCaptchaStore 使用。"""
    fake_mod = types.ModuleType("redis")
    fake_async = types.ModuleType("redis.asyncio")
    fake_async.from_url = lambda url, **kw: fake
    fake_mod.asyncio = fake_async
    sys.modules.pop("redis", None)
    sys.modules.pop("redis.asyncio", None)
    sys.modules["redis"] = fake_mod
    sys.modules["redis.asyncio"] = fake_async
    return fake_mod


def _restore_redis():
    sys.modules.pop("redis", None)
    sys.modules.pop("redis.asyncio", None)


@pytest.mark.asyncio
async def test_redis_store_shared_atomic_consume_and_fallback():
    """Redis 后端：跨 worker 共享、原子消费；Redis 故障回退内存。"""
    fake = _FakeRedis()
    fake_mod = await _install_fake_redis(fake)
    try:
        from app.services.captcha_service import RedisCaptchaStore

        store = RedisCaptchaStore("redis://fake:6379/0", ttl_seconds=300)

        # 生成 -> 写入共享存储
        captcha_id, code = await store.generate()
        assert code in fake.data.values()

        # 两个“worker”先后消费同一 captcha_id：仅第一次成功（原子一次性）
        assert await store.consume(captcha_id) == code
        assert await store.consume(captcha_id) is None
    finally:
        _restore_redis()

    # 新实例（模拟另一个进程）在 Redis 故障时回退到内存，功能不中断
    fake2 = _FakeRedis()
    fake2.fail = True
    fake_mod2 = await _install_fake_redis(fake2)
    try:
        from app.services.captcha_service import RedisCaptchaStore

        store2 = RedisCaptchaStore("redis://fake:6379/0", ttl_seconds=300)
        cid, ccode = await store2.generate()
        assert len(ccode) == 6
        assert await store2.consume(cid) == ccode
    finally:
        _restore_redis()


@pytest.mark.asyncio
async def test_get_store_selects_redis_when_redis_url_configured():
    """配置 REDIS_URL 后，全局验证码存储应自动切换到 Redis 后端。"""
    from app.core.config import settings
    from app.services.captcha_service import get_captcha_store, reset_captcha_store_for_tests, RedisCaptchaStore
    fake = _FakeRedis()
    await _install_fake_redis(fake)
    reset_captcha_store_for_tests()
    try:
        with patch.object(settings, "REDIS_URL", "redis://fake:6379/0"):
            store = get_captcha_store()
        assert isinstance(store, RedisCaptchaStore)
    finally:
        reset_captcha_store_for_tests()
        _restore_redis()


@pytest.mark.asyncio
async def test_get_store_falls_back_to_memory_when_redis_init_fails():
    """REDIS_URL 配置了但 Redis 初始化异常时，应回退内存（fail-open）。"""
    from app.core.config import settings
    from app.services.captcha_service import get_captcha_store, reset_captcha_store_for_tests, MemoryCaptchaStore
    fake = _FakeRedis()
    # 让 from_url 报错，模拟服务不可用
    def _boom(url, **kw):
        raise ConnectionError("redis down")
    fake_mod = await _install_fake_redis(fake)
    fake_mod.asyncio.from_url = _boom
    reset_captcha_store_for_tests()
    try:
        with patch.object(settings, "REDIS_URL", "redis://fake:6379/0"):
            store = get_captcha_store()
        assert isinstance(store, MemoryCaptchaStore)
    finally:
        reset_captcha_store_for_tests()
        _restore_redis()