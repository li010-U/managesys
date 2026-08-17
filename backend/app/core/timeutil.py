"""Local-time helper.

All business timestamps are written, compared and displayed as local (Asia/Shanghai) naive
time. SQLite DateTime(timezone=True) drops tzinfo on read, so naive datetime is the single
internal convention. Previously values were stored as UTC but displayed as local, causing an
8-hour display drift; now storage and display are unified on local time.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def now_local(*args) -> datetime:
    """SQLAlchemy default/onupdate callable: returns local naive now, tolerant of context args."""
    return datetime.now()


def now() -> datetime:
    """Local naive current time (Asia/Shanghai), used for writes and comparisons."""
    return datetime.now()


def utcnow() -> datetime:
    """Aware UTC current time, only for protocol-level use (e.g. JWT)."""
    return datetime.now(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Normalize to local naive; aware input is converted to local then tz stripped."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Alias of ensure_utc."""
    return ensure_utc(dt)


def fmt_iso(dt: Optional[datetime]) -> str:
    """Local ISO string; None -> empty string."""
    ndt = ensure_utc(dt)
    return ndt.isoformat() if ndt is not None else ""

