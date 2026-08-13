# -*- coding: utf-8 -*-
"""时区工具单元测试：确保 nice、aware 混用不会抛 TypeError。
对应优化方案第③项“统一时间时区处理”。
"""
from datetime import datetime, timezone, timedelta
import pytest
from app.core.timeutil import utcnow, ensure_utc, fmt_iso


def test_ensure_utc_naive_is_tagged_utc():
    naive = datetime(2026, 1, 1, 12, 0, 0)
    out = ensure_utc(naive)
    assert out.tzinfo is not None
    assert out.utcoffset() == timedelta(0)


def test_ensure_utc_aware_is_normalized():
    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    out = ensure_utc(aware)
    assert out.tzinfo == timezone.utc
    assert out.hour == 4  # 12:00 +08 -> 04:00 UTC


def test_ensure_utc_none():
    assert ensure_utc(None) is None


def test_naive_aware_comparison_is_safe():
    # 这是本次早前登录 500 的根因：
    # 用 ensure_utc 后可以安全地将 DB 读回的 naive 时刻与 aware now 比较。
    db_locked_until = datetime(2026, 8, 13, 9, 20, 0)  # naive, 仿 DB 读回
    now = utcnow()
    locked = ensure_utc(db_locked_until)
    # 不会抛 TypeError：两者都是 aware
    result = locked > now
    assert isinstance(result, bool)


def test_utcnow_is_aware():
    assert utcnow().tzinfo is not None
    assert utcnow().utcoffset() == timedelta(0)


def test_fmt_iso_none_empty():
    assert fmt_iso(None) == ""
