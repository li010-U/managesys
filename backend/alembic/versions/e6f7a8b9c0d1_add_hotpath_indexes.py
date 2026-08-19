# -*- coding: utf-8 -*-
"""???????????????/?????

- sensor_data(sensor_id, recorded_at)?????? 180 ?????????
- alerts(status, created_at)????????+????/??
- audit_logs(created_at)??????????/??????
- login_logs(created_at)??????????

??? __table_args__ ?????create_all ??????????????
CREATE INDEX IF NOT EXISTS ????????? SQLite ? PostgreSQL?

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-08-18
"""
from typing import Sequence, Union

from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_INDEXES = [
    ("ix_sensor_data_sensor_id_recorded_at", "sensor_data", ["sensor_id", "recorded_at"]),
    ("ix_alerts_status_created_at", "alerts", ["status", "created_at"]),
    ("ix_audit_logs_created_at", "audit_logs", ["created_at"]),
    ("ix_login_logs_created_at", "login_logs", ["created_at"]),
]


def upgrade() -> None:
    conn = op.get_bind()
    for name, table, cols in _INDEXES:
        try:
            op.execute(
                "CREATE INDEX IF NOT EXISTS %s ON %s (%s)"
                % (name, table, ", ".join(cols))
            )
        except Exception as _e:  # ?????/??????????
            pass


def downgrade() -> None:
    for name, _table, _cols in reversed(_INDEXES):
        try:
            op.execute("DROP INDEX IF EXISTS %s" % name)
        except Exception:
            pass
