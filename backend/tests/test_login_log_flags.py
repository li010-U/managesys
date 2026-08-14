# -*- coding: utf-8 -*-
"""Unit tests for login-log brute-force flag logic."""

from types import SimpleNamespace
from datetime import datetime, timedelta

from app.api.v1.auth import _detect_brute_force_ips


def _rec(status, ip, created_at):
    return SimpleNamespace(login_status=status, ip_address=ip, created_at=created_at)


def test_burst_within_window_is_flagged():
    base = datetime(2026, 8, 14, 10, 0, 0)
    logs = [_rec('fail', '10.0.0.5', base + timedelta(seconds=i * 30)) for i in range(6)]
    assert _detect_brute_force_ips(logs) == {'10.0.0.5'}


def test_scattered_failures_not_flagged():
    base = datetime(2026, 8, 14, 10, 0, 0)
    logs = [_rec('fail', '10.0.0.6', base + timedelta(seconds=i * 30)) for i in range(4)]
    assert _detect_brute_force_ips(logs) == set()


def test_success_logins_never_flagged():
    base = datetime(2026, 8, 14, 10, 0, 0)
    logs = [
        _rec('success', '10.0.0.7', base),
        _rec('success', '10.0.0.7', base + timedelta(seconds=10)),
    ]
    logs += [_rec('fail', '10.0.0.7', base + timedelta(seconds=i * 60 + 20)) for i in range(4)]
    assert _detect_brute_force_ips(logs) == set()


def test_five_failures_within_window_flag_despite_successes():
    base = datetime(2026, 8, 14, 10, 0, 0)
    logs = [_rec('success', '10.0.0.8', base)]
    logs += [_rec('fail', '10.0.0.8', base + timedelta(seconds=i * 30 + 5)) for i in range(5)]
    assert _detect_brute_force_ips(logs) == {'10.0.0.8'}


def test_failures_spread_beyond_window_not_flagged():
    base = datetime(2026, 8, 14, 10, 0, 0)
    logs = [_rec('fail', '10.0.0.9', base + timedelta(minutes=i * 10)) for i in range(5)]
    assert _detect_brute_force_ips(logs) == set()

