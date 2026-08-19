# -*- coding: utf-8 -*-
"""告警生命周期：Alert 自动恢复/去重/偶发字段 + 环境气象与偶发事件表。

- 为 alerts 增加 last_abnormal_at / normal_since_at / auto_resolve_minutes /
  duration_seconds / is_transient / cooldown_until / lifecycle_action 字段。
- 新增 env_weather_records（环境/气象数据）与 transient_failure_events
  （偶发故障事件留痕）两张表。

采用与既有迁移一致的幂等守卫（列/表存在性检查），兼容新库与存量库。

Revision ID: d4e5f6a7b8c9
Revises: c3d0be78b8c9
Create Date: 2026-08-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d0be78b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table: str, column: str) -> bool:
    insp = sa.inspect(conn)
    try:
        cols = [c["name"] for c in insp.get_columns(table)]
    except Exception:
        return False
    return column in cols


def _has_table(conn, table: str) -> bool:
    insp = sa.inspect(conn)
    try:
        return table in insp.get_table_names()
    except Exception:
        return False


_ALERT_COLUMNS = [
    ("alerts", "last_abnormal_at", "DATETIME"),
    ("alerts", "normal_since_at", "DATETIME"),
    ("alerts", "auto_resolve_minutes", "INTEGER DEFAULT 30"),
    ("alerts", "duration_seconds", "INTEGER"),
    ("alerts", "is_transient", "BOOLEAN DEFAULT 0"),
    ("alerts", "cooldown_until", "DATETIME"),
    ("alerts", "lifecycle_action", "VARCHAR(24)"),
]


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    for table, col, type_sql in _ALERT_COLUMNS:
        if not _has_column(conn, table, col):
            op.execute(f"ALTER TABLE {table} ADD COLUMN {col} {type_sql}")

    # 环境/气象数据表
    if not _has_table(conn, "env_weather_records"):
        op.execute("""
            CREATE TABLE env_weather_records (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER,
                location_name VARCHAR(128),
                temperature FLOAT,
                humidity FLOAT,
                weather VARCHAR(32),
                windspeed FLOAT,
                recorded_at DATETIME,
                created_at DATETIME
            )
        """)
    # 偶发故障事件表
    if not _has_table(conn, "transient_failure_events"):
        op.execute("""
            CREATE TABLE transient_failure_events (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                alert_id INTEGER,
                target_type VARCHAR(32) NOT NULL,
                target_id VARCHAR(64) NOT NULL,
                metric VARCHAR(64),
                title VARCHAR(256) NOT NULL,
                started_at DATETIME NOT NULL,
                recovered_at DATETIME,
                duration_seconds INTEGER DEFAULT 0,
                env_temperature FLOAT,
                env_humidity FLOAT,
                env_weather VARCHAR(32),
                env_windspeed FLOAT,
                location_id INTEGER,
                location_name VARCHAR(128),
                created_at DATETIME
            )
        """)
        op.execute("CREATE INDEX IF NOT EXISTS ix_transient_target_id ON transient_failure_events(target_id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_transient_started_at ON transient_failure_events(started_at)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_alert_last_abnormal_at ON alerts(last_abnormal_at)")


def downgrade() -> None:
    pass
