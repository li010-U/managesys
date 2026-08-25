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


# PG 无 DATETIME 类型，用 TIMESTAMP；SQLite 保持 DATETIME。此处存原始 SQLite 风格，
# 实际执行时在 upgrade 中按 dialect 替换为 TIMESTAMP/DATETIME。
_ALERT_COLUMNS = [
    ("alerts", "last_abnormal_at", None),
    ("alerts", "normal_since_at", None),
    ("alerts", "auto_resolve_minutes", "INTEGER DEFAULT 30"),
    ("alerts", "duration_seconds", "INTEGER"),
    ("alerts", "is_transient", "BOOLEAN DEFAULT 0"),
    ("alerts", "cooldown_until", None),
    ("alerts", "lifecycle_action", "VARCHAR(24)"),
]


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name

    # None 表示该列是时间字段：PG 用 TIMESTAMP，SQLite 保持 DATETIME。
    datetime_type = "TIMESTAMP" if dialect == "postgresql" else "DATETIME"
    for table, col, type_sql in _ALERT_COLUMNS:
        if not _has_column(conn, table, col):
            op.execute(f"ALTER TABLE {table} ADD COLUMN {col} {type_sql or datetime_type}")

    # 环境/气象数据表
    if not _has_table(conn, "env_weather_records"):
        op.create_table(
            'env_weather_records',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('location_id', sa.Integer(), nullable=True),
            sa.Column('location_name', sa.String(length=128), nullable=True),
            sa.Column('temperature', sa.Float(), nullable=True),
            sa.Column('humidity', sa.Float(), nullable=True),
            sa.Column('weather', sa.String(length=32), nullable=True),
            sa.Column('windspeed', sa.Float(), nullable=True),
            sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
    # 偶发故障事件表
    if not _has_table(conn, "transient_failure_events"):
        op.create_table(
            'transient_failure_events',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('alert_id', sa.Integer(), nullable=True),
            sa.Column('target_type', sa.String(length=32), nullable=False),
            sa.Column('target_id', sa.String(length=64), nullable=False),
            sa.Column('metric', sa.String(length=64), nullable=True),
            sa.Column('title', sa.String(length=256), nullable=False),
            sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
            sa.Column('recovered_at', sa.DateTime(timezone=True), nullable=True),
            sa.Column('duration_seconds', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('env_temperature', sa.Float(), nullable=True),
            sa.Column('env_humidity', sa.Float(), nullable=True),
            sa.Column('env_weather', sa.String(length=32), nullable=True),
            sa.Column('env_windspeed', sa.Float(), nullable=True),
            sa.Column('location_id', sa.Integer(), nullable=True),
            sa.Column('location_name', sa.String(length=128), nullable=True),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint('id'),
        )
        op.execute("CREATE INDEX IF NOT EXISTS ix_transient_target_id ON transient_failure_events(target_id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_transient_started_at ON transient_failure_events(started_at)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_alert_last_abnormal_at ON alerts(last_abnormal_at)")


def downgrade() -> None:
    pass
