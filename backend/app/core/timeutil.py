# -*- coding: utf-8 -*-
"""统一时间时区处理工具。

SQLite/SQLAlchemy 存日期时（DateTime(timezone=True)）其实会丢失 tzinfo，
读回来的都是 naive datetime；而业务代码用 datetime.now(timezone.utc)
得到 aware datetime。两者直接比较/-会抛 TypeError
(can't compare offset-naive and offset-aware datetimes)。

所有时刻：创建/写入用 utcnow()，读出后比较前用 ensure_utc()。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    """时区-aware 的当前 UTC 时刻，用于写入与比较。"""
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """将任意 datetime 规范化为 aware UTC。
    - naive 输入：默认视为 UTC 并打标；
    - aware 输入：转换到 UTC。
    返回保证是 aware，无不同时区比较问题。
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """ensure_utc 的别名（便于调用。"""
    return ensure_utc(dt)


def fmt_iso(dt: Optional[datetime]) -> str:
    """输出带时区的 ISO 字符串；None -> ""。"""
    u = ensure_utc(dt)
    return u.isoformat() if u is not None else ""
