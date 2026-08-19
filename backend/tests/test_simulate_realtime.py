# -*- coding: utf-8 -*-
"""实时传感器模拟器(simulate_realtime)清理逻辑回归测试。"""
import sqlite3
from datetime import datetime, timedelta

import pytest

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
if str(_BACKEND / "dev_tools") not in sys.path:
    sys.path.insert(0, str(_BACKEND / "dev_tools"))

from dev_tools.simulate_realtime import _cleanup_sensor_data


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "sim.db"
    con = sqlite3.connect(str(db_path))
    con.execute(
        "CREATE TABLE sensor_data ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT,"
        " sensor_id INTEGER, value REAL, recorded_at TEXT, source_mark TEXT)"
    )
    yield con
    con.close()


def _insert(con, source_mark, hours_ago):
    ts = (datetime.now() - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S.%f")
    con.execute(
        "INSERT INTO sensor_data (sensor_id, value, recorded_at, source_mark) VALUES (1, ?, ?, ?)",
        (1.0, ts, source_mark),
    )


def test_cleanup_removes_old_normal_sim_only(conn):
    # 超期的正常(sim)数据应被删除
    _insert(conn, "sim", 30)  # 30小时前：超过24h，删
    _insert(conn, "sim", 2)   # 2小时前：保留
    # 超期的异常(abnormal)数据必须保留（由后端180天管理）
    _insert(conn, "abnormal", 30)  # 30小时前：异常，不删
    conn.commit()

    _cleanup_sensor_data(conn, keep_hours=24.0, keep_rows=0)
    rows = conn.execute("SELECT source_mark, recorded_at FROM sensor_data ORDER BY value").fetchall()
    marks = [r[0] for r in rows]
    assert marks == ["sim", "abnormal"], f"got {marks}"
    # 只剩 2小时前的 sim 和 30小时前的 abnormal


def test_cleanup_keep_rows_caps_abnormal(conn):
    # keep_rows 兜底应只裁剪异常数据到指定行数
    for i in range(5):
        _insert(conn, "abnormal", 24 + i)  # 全部超24h
    _insert(conn, "sim", 1)
    conn.commit()

    _cleanup_sensor_data(conn, keep_hours=24.0, keep_rows=2)
    abnormal_count = conn.execute(
        "SELECT COUNT(*) FROM sensor_data WHERE source_mark='abnormal'"
    ).fetchone()[0]
    assert abnormal_count == 2
    # 正常 sim 数据（即使超过24h）会被删，仅保留最新的（此处2小时前的不超期）
    sim_count = conn.execute(
        "SELECT COUNT(*) FROM sensor_data WHERE source_mark='sim'"
    ).fetchone()[0]
    assert sim_count == 1
