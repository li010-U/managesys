# -*- coding: utf-8 -*-
"""Timezone utility unit tests.
Convention: all business timestamps are stored/compared/displayed as local naive time
(Asia/Shanghai). ensure_utc normalizes aware input to local naive and is identity for naive.
"""
from datetime import datetime, timezone, timedelta

from app.core.timeutil import utcnow, ensure_utc, fmt_iso, now


def test_ensure_utc_naive_is_unchanged():
    naive = datetime(2026, 1, 1, 12, 0, 0)
    out = ensure_utc(naive)
    assert out == naive
    assert out.tzinfo is None


def test_ensure_utc_aware_is_local_naive():
    aware = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone(timedelta(hours=8)))
    out = ensure_utc(aware)
    assert out.tzinfo is None
    assert out == aware.replace(tzinfo=None)


def test_ensure_utc_none():
    assert ensure_utc(None) is None


def test_naive_local_comparison_is_safe():
    db_naive = datetime(2026, 8, 13, 9, 20, 0)  # naive local read from DB
    now_val = now()
    locked = ensure_utc(db_naive)
    assert isinstance(locked > now_val, bool)


def test_now_is_naive_local():
    assert now().tzinfo is None


def test_utcnow_is_aware_utc():
    assert utcnow().tzinfo is not None
    assert utcnow().utcoffset() == timedelta(0)


def test_fmt_iso_none_empty():
    assert fmt_iso(None) == ""


def test_fmt_iso_local_output():
    assert fmt_iso(datetime(2026, 1, 1, 9, 0, 0)) == "2026-01-01T09:00:00"

