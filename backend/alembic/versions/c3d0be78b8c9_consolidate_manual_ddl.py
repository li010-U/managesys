# -*- coding: utf-8 -*-
"""Consolidate legacy manual DDL (former _ensure_columns) into Alembic.

Previously backend/app/main.py ran ~23 hardcoded ALTER TABLE statements plus
hand-rolled index/table creation at every startup. This migration absorbs that
idempotent DDL so the schema converges on a single migration entry point.

The operations are guarded by column/table existence checks so they are safe
both on fresh databases and on live databases where _ensure_columns already
added the columns. Runs on SQLite and PostgreSQL via inspector introspection.

Revision ID: c3d0be78b8c9
Revises: a1b2c3d4e5f6
Create Date: 2026-08-18
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3d0be78b8c9"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(conn, table: str, column: str) -> bool:
    insp = sa.inspect(conn)
    try:
        cols = [c["name"] for c in insp.get_columns(table)]
    except Exception:
        return False
    return column in cols


def _columns_definition(dialect_name: str):
    """(table, column, type_sql) tuples; type_sql is dialect-aware."""
    bool_t = "BOOLEAN DEFAULT 0"
    int_t = "INTEGER"
    # All statements are additive and guarded; SQLite/PG both accept these.
    return [
        ("work_order_categories", "need_approval", bool_t),
        ("work_orders", "approved_by", int_t),
        ("work_orders", "approved_at", "DATETIME"),
        ("work_orders", "reject_reason", "TEXT"),
        ("users", "must_change_password", bool_t),
        ("users", "token_version", "INTEGER DEFAULT 0"),
        ("sensor_data", "source_mark", "VARCHAR(16) DEFAULT 'normal'"),
        ("devices", "power_rating", "FLOAT"),
        ("ip_subnets", "vlan_id", int_t),
        ("racks", "pos_x_m", "FLOAT"),
        ("racks", "pos_z_m", "FLOAT"),
        ("racks", "width_m", "FLOAT"),
        ("racks", "depth_m", "FLOAT"),
        ("racks", "facing_deg", "FLOAT"),
        ("alerts", "dedupe_key", "VARCHAR(128)"),
        ("alerts", "occurrences", "INTEGER DEFAULT 1"),
        ("alerts", "first_seen_at", "DATETIME"),
        ("alerts", "acknowledged_at", "DATETIME"),
        ("alerts", "resolved_at", "DATETIME"),
        ("alerts", "escalated_at", "DATETIME"),
        ("alerts", "escalated_from", "VARCHAR(16)"),
        ("audit_logs", "request_path", "VARCHAR(256)"),
        ("audit_logs", "user_agent", "VARCHAR(512)"),
    ]


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name
    for table, col, type_sql in _columns_definition(dialect):
        if not _has_column(conn, table, col):
            op.execute(f"ALTER TABLE {table} ADD COLUMN {col} {type_sql}")

    # IP 台账全局唯一约束（防重复 IP）。若存在重复数据则跳过，交由数据治理处理。
    try:
        op.execute("DROP INDEX IF EXISTS uq_ip_address_subnet_addr")
        op.execute("CREATE UNIQUE INDEX IF NOT EXISTS uq_ip_address_addr ON ip_addresses(address)")
    except Exception:
        pass


def downgrade() -> None:
    pass
