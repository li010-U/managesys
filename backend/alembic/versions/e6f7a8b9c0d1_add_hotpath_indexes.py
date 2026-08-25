# -*- coding: utf-8 -*-
"""为数据热点路径补充复合索引。

- sensor_data(sensor_id, recorded_at)：支撑 180 天传感器历史查询
- alerts(status, created_at)：支撑状态过滤 + 泛化/排序
- audit_logs(created_at)：支撑审计日志清理与分页
- login_logs(created_at)：支撑登录日志清理

通过 __table_args__ 定义，保证 create_all 与表中结构一致；
CREATE INDEX IF NOT EXISTS 保证在 SQLite 与 PostgreSQL 上均可重复执行。
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
        except Exception as _e:  # 该索引可能已存在（跨方言），跳过
            pass


def downgrade() -> None:
    for name, _table, _cols in reversed(_INDEXES):
        try:
            op.execute("DROP INDEX IF EXISTS %s" % name)
        except Exception:
            pass
