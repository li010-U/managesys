# -*- coding: utf-8 -*-
"""备份工具回归测试：pg_dump/pg_restore 定位与 DSN 转换。"""
import os

import pytest

import backup_utils
from app import core as _core


def test_resolve_pg_tool_finds_pg_dump():
    """应找到 pg_dump（本机或常见安装目录），至少返回非空名。"""
    tool = backup_utils._resolve_pg_tool("pg_dump")
    assert isinstance(tool, str) and tool
    if tool.lower().endswith(".exe"):
        assert os.path.isfile(tool)


def test_using_pg_and_pg_dsn_consistent():
    """_using_pg() 与 _pg_dsn() 应反映同一份配置，互不矛盾。"""
    using_pg = backup_utils._using_pg()
    assert using_pg in (True, False)
    dsn = backup_utils._pg_dsn()
    assert isinstance(dsn, str)
    if using_pg:
        assert dsn.startswith("postgresql://")
    else:
        assert ("sqlite" in dsn) or dsn


def test_pg_dsn_sync_conversion(monkeypatch):
    """asyncpg URL 应被转为 psql/pg_dump 可用的同步 postgresql DSN。"""
    monkeypatch.setattr(
        _core.config.settings, "DATABASE_URL",
        "postgresql+asyncpg://u:pw@127.0.0.1:5433/db",
    )
    assert backup_utils._pg_dsn() == "postgresql://u:pw@127.0.0.1:5433/db"
