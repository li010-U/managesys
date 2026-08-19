# -*- coding: utf-8 -*-
"""验证码生成与验证服务。

验证码存储采用「可插拔后端」：
- 默认 MemoryCaptchaStore（进程内内存，单 worker 部署零成本，行为与原实现完全一致）
- 配置 REDIS_URL 后使用 RedisCaptchaStore（多 worker 共享、原子一次性消费），
  从根本上消除跨进程“验证码明明正确却提示错误”的问题。

性能与可靠性设计：
- 未配置 Redis 时全部操作在进程内完成，无任何额外网络往返，对整体性能零影响。
- 配置 Redis 后，验证码仅在登录/生成路径各产生一次原子 GETDEL/SET，延迟可忽略。
- Redis 不可用时自动回退内存存储（fail-open），绝不阻塞/锁定用户登录。
"""
from __future__ import annotations

import asyncio
import io
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings

CAPTCHA_TTL_SECONDS: int = settings.CAPTCHA_TTL_SECONDS

_CAPTCHA_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def _generate_code(length: int = 6) -> str:
    """生成随机字母数字验证码（排除易混淆字符），默认长度 6 位。"""
    return ''.join(random.choices(_CAPTCHA_ALPHABET, k=length))


def _create_captcha_image(code: str) -> bytes:
    """生成验证码图片（宽度按字符数自适应）。"""
    height = 40
    char_step = 22
    width = 8 + len(code) * char_step + 8
    img = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(img)

    for _ in range(random.randint(50, 100)):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        draw.point((x, y), fill=(random.randint(100, 200), random.randint(100, 200), random.randint(100, 200)))

    for _ in range(random.randint(2, 4)):
        x1 = random.randint(0, width // 3)
        y1 = random.randint(0, height)
        x2 = random.randint(width * 2 // 3, width - 1)
        y2 = random.randint(0, height)
        draw.line((x1, y1, x2, y2), fill=(random.randint(150, 220),) * 3, width=1)

    try:
        font = ImageFont.truetype("arial.ttf", 26)
    except (IOError, OSError):
        font = ImageFont.load_default()

    x_offset = 8
    for char in code:
        y_offset = random.randint(5, 12)
        color = (random.randint(0, 90), random.randint(0, 90), random.randint(0, 90))
        draw.text((x_offset, y_offset), char, fill=color, font=font)
        x_offset += char_step

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _matches(raw_code: Optional[str], submitted: str) -> bool:
    """大小写不敏感、容忍首尾空白的比对。"""
    if not raw_code:
        return False
    return str(raw_code).lower() == str(submitted).strip().lower()


class MemoryCaptchaStore:
    """进程内内存验证码存储（单 worker / 未配置 Redis 时的默认实现）。"""

    def __init__(self, ttl_seconds: int = CAPTCHA_TTL_SECONDS, max_entries: int = 512) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._cache: Dict[str, Dict[str, object]] = {}

    async def generate(self) -> Tuple[str, str]:
        """生成并缓存验证码，返回 (captcha_id, code)。"""
        code = _generate_code()
        captcha_id = str(uuid.uuid4())
        self._cache[captcha_id] = {
            "code": code,
            "expires_at": datetime.now() + timedelta(seconds=self.ttl_seconds),
        }
        if len(self._cache) > self.max_entries:
            now = datetime.now()
            expired = [k for k, v in self._cache.items() if v["expires_at"] < now]
            for k in expired:
                self._cache.pop(k, None)
        return captcha_id, code

    async def consume(self, captcha_id: str) -> Optional[str]:
        """原子消费：取走并删除该验证码对应的明文，返回明文；不存在或已消费返回 None。"""
        record = self._cache.pop(captcha_id, None)
        if not record:
            return None
        if datetime.now() > record["expires_at"]:
            return None
        return record["code"]

    async def close(self) -> None:
        pass


class RedisCaptchaStore:
    """基于 Redis 的共享验证码存储（多 worker 集中、原子一次性消费）。

    - generate: SETNX/GETSET？不使用，直接用 SET with EX（键为 captcha_id，值为明文）。
    - consume: 原子 GETDEL —— 恰好一个请求能取到明文并删除，天然一次性。
    - Redis 故障时回退到进程内内存存储（fail-open），保可用性、不锁用户。
    """

    REDIS_PREFIX: str = settings.CAPTCHA_REDIS_PREFIX

    def __init__(self, redis_url: str, ttl_seconds: int = CAPTCHA_TTL_SECONDS) -> None:
        import redis.asyncio as aioredis
        self.ttl_seconds = ttl_seconds
        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._fallback = MemoryCaptchaStore(ttl_seconds=ttl_seconds)

    async def generate(self) -> Tuple[str, str]:
        code = _generate_code()
        captcha_id = str(uuid.uuid4())
        key = self.REDIS_PREFIX + captcha_id
        try:
            await self._redis.set(key, code, ex=self.ttl_seconds)
            return captcha_id, code
        except Exception:
            # Redis 不可用：回退内存，保证验证码功能不中断
            fid, fcode = await self._fallback.generate()
            return fid, fcode

    async def consume(self, captcha_id: str) -> Optional[str]:
        if not captcha_id:
            return None
        key = self.REDIS_PREFIX + captcha_id
        try:
            raw: Optional[str] = await self._redis.getdel(key)
            return raw
        except Exception:
            # Redis 不可用：回退内存
            return await self._fallback.consume(captcha_id)

    async def close(self) -> None:
        try:
            await self._redis.aclose()
        except Exception:
            pass


# ---- 全局单例：按 REDIS_URL 选择后端（与 ratelimit.build_limiter 同一约定） ----

_captcha_store: Optional[object] = None


def get_captcha_store() -> object:
    global _captcha_store
    if _captcha_store is None:
        try:
            if settings.REDIS_URL:
                _captcha_store = RedisCaptchaStore(settings.REDIS_URL)
            else:
                _captcha_store = MemoryCaptchaStore()
        except Exception:
            import logging
            logging.getLogger("app").warning("验证码 Redis 存储初始化失败，回退内存存储")
            _captcha_store = MemoryCaptchaStore()
    return _captcha_store


def reset_captcha_store_for_tests() -> None:
    """测试辅助：重建存储单例，便于对后端选择做隔离测试。"""
    global _captcha_store
    _captcha_store = None


async def generate_captcha_async() -> Tuple[str, str, bytes]:
    """异步生成验证码，返回 (captcha_id, code_text, image_bytes)。"""
    store = get_captcha_store()
    captcha_id, code = await store.generate()  # type: ignore[attr-defined]
    img_bytes = _create_captcha_image(code)
    return captcha_id, code, img_bytes


async def verify_captcha_async(captcha_id: str, captcha_code: str) -> bool:
    """异步校验验证码（一次性消费）。"""
    if not captcha_id or not captcha_code:
        return False
    store = get_captcha_store()
    raw = await store.consume(captcha_id)  # type: ignore[attr-defined]
    return _matches(raw, captcha_code)


def generate_captcha() -> Tuple[str, str, bytes]:
    """同步生成验证码（兼容旧接口与同步测试；仅用于无运行中事件循环的上下文）。

    说明：FastAPI 异步路由请使用 generate_captcha_async()，避免在运行中的
    事件循环里调用本函数引发 run_until_complete 冲突。
    """
    return asyncio.run(generate_captcha_async())


def verify_captcha(captcha_id: str, captcha_code: str) -> bool:
    """同步校验验证码（兼容旧接口与同步测试；仅用于无运行中事件循环的上下文）。"""
    return asyncio.run(verify_captcha_async(captcha_id, captcha_code))
