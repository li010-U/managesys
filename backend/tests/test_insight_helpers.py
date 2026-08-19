# -*- coding: utf-8 -*-
"""洞察/传感器聚合边界分支回归测试。

覆盖 sensor_service._downsample / _summarize_bucket 与
insight_service._robust_bounds / _linear_forecast / _growth_and_power_trend
的空数据、极简数据、历史不足、极端值等边界，避免"拆东墙补西墙"式回归。
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services import sensor_service
from app.services.insight_service import (
    _growth_and_power_trend,
    _linear_forecast,
    _robust_bounds,
)


# ---------- _downsample / _summarize_bucket ----------

def _row(value, recorded_at):
    """构造一个模拟 SensorData 行的轻量对象（仅含 _downsample 用到的字段）。"""
    return SimpleNamespace(
        id=1, sensor_id=1, value=value,
        recorded_at=recorded_at, source_mark="normal",
    )


def test_downsample_empty_returns_empty_list():
    assert sensor_service._downsample([], 10) == []


def test_downsample_single_row():
    t = datetime(2026, 1, 1, 12, 0, 0)
    out = sensor_service._downsample([_row(3.5, t)], 10)
    assert len(out) == 1
    assert out[0].value == pytest.approx(3.5)


def test_downsample_rows_leq_maxpoints_reverses_newest_first():
    # 行数 <= max_points：不聚合，直接倒序（最新在前）
    rows = [_row(1.0, datetime(2026, 1, 1, 10, 0, 0)),
            _row(2.0, datetime(2026, 1, 1, 11, 0, 0)),
            _row(3.0, datetime(2026, 1, 1, 12, 0, 0))]
    out = sensor_service._downsample(rows, max_points=5)
    assert [p.value for p in out] == [3.0, 2.0, 1.0]


def test_downsample_rows_gt_maxpoints_buckets_average():
    # 行数 > max_points：等分桶，桶内取均值，仍倒序（最新在前）
    rows = [_row(float(i), datetime(2026, 1, 1, i // 4, 0, 0)) for i in range(1, 21)]
    out = sensor_service._downsample(rows, max_points=5)
    assert len(out) <= 5
    # 桶均值 = 桶内样本均值；整体先后顺序与输入相反
    assert out[0].value >= out[-1].value


def test_downsample_bucket_summary_takes_mid_sample():
    # _summarize_bucket：取中位样本的 recorded_at / id，值为桶内均值
    rows = [_row(1.0, datetime(2026, 1, 1, 0, 0, 0)),
            _row(3.0, datetime(2026, 1, 1, 1, 0, 0)),
            _row(5.0, datetime(2026, 1, 1, 2, 0, 0))]
    s = sensor_service._summarize_bucket(rows)
    assert s.value == pytest.approx(3.0)  # (1+3+5)/3
    assert s.recorded_at == rows[1].recorded_at  # 中点样本
    assert s.source_mark == "normal"


# ---------- _robust_bounds ----------

def test_robust_bounds_empty():
    assert _robust_bounds([]) == (None, None)


def test_robust_bounds_iqr_when_enough_and_spread():
    lo, hi = _robust_bounds([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    # IQR 下界应低于最小值、上界应高于最大值（k=1.5）
    assert lo < 1
    assert hi > 10


def test_robust_bounds_fallback_when_no_spread():
    # 全部相同 -> IQR=0，回退均值±2sd（sd=0 -> 同值区间）
    lo, hi = _robust_bounds([5, 5, 5, 5])
    assert lo == pytest.approx(5.0)
    assert hi == pytest.approx(5.0)


def test_robust_bounds_fallback_few_values():
    # 少于 4 个 -> 均值±2sd 兜底：区间覆盖样本且不穿透到同值
    lo, hi = _robust_bounds([10, 20, 30])
    assert lo < 10
    assert hi > 30
    assert lo < hi


def test_robust_bounds_single_value():
    lo, hi = _robust_bounds([42])
    assert lo == pytest.approx(42.0)
    assert hi == pytest.approx(42.0)


# ---------- _linear_forecast ----------

def test_linear_forecast_too_few_points_returns_none():
    assert _linear_forecast([1.0, 2.0], steps=3) is None


def test_linear_forecast_flat_series_slope_zero():
    out = _linear_forecast([5.0, 5.0, 5.0, 5.0], steps=3)
    assert out is not None
    assert len(out) == 3
    for p in out:
        assert p["value"] == pytest.approx(5.0)


def test_linear_forecast_rising_series_shape():
    out = _linear_forecast([1.0, 2.0, 3.0, 4.0], steps=2)
    assert out is not None
    assert len(out) == 2
    for p in out:
        assert "value" in p and "low" in p and "high" in p
        assert p["low"] <= p["value"] <= p["high"]


# ---------- _growth_and_power_trend ----------

def _dev(start_u, end_u, created_at, power=1.0):
    return SimpleNamespace(start_u=start_u, end_u=end_u, created_at=created_at, power_rating=power)


def test_growth_no_valid_points():
    r = _growth_and_power_trend([])
    assert r["has_history"] is False
    assert r["occupied_now"] == 0
    assert r["monthly_growth"] is None


def test_growth_short_history_not_overestimated():
    now = datetime.now(timezone.utc)
    devices = [
        _dev(1, 2, now - timedelta(days=5)),
        _dev(3, 3, now - timedelta(days=3)),
    ]
    r = _growth_and_power_trend(devices)
    # 历史不足 30 天：标记为经验估算，不给出高估的月增速
    assert r["has_history"] is False
    assert r["monthly_growth"] is None


def test_growth_long_history_reports_growth():
    now = datetime.now(timezone.utc)
    devices = [
        _dev(1, 2, now - timedelta(days=90)),
        _dev(3, 4, now - timedelta(days=60)),
        _dev(5, 6, now - timedelta(days=30)),
    ]
    r = _growth_and_power_trend(devices)
    assert r["has_history"] is True
    assert r["occupied_now"] == 6  # 2 + 2 + 2
    assert r["monthly_growth"] is not None and r["monthly_growth"] > 0
    assert len(r["history"]) == 3


def test_growth_monthly_capped_at_48():
    # 30 天窗口内大量上架（100 U 位）-> 月增速应被上限钳制，避免显示离谱数值
    now = datetime.now(timezone.utc)
    n = 100
    devices = [
        _dev(i, i, now - timedelta(days=30 * (1 - i / (n - 1))), power=1.0)
        for i in range(n)
    ]
    r = _growth_and_power_trend(devices)
    assert r["has_history"] is True
    assert r["occupied_now"] == n
    assert r["monthly_growth"] <= 48.0
