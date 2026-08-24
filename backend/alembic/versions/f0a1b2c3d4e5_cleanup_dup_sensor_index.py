# -*- coding: utf-8 -*-
"""清理 sensor_data 上遗留的重复索引。

- idx_sensor_data_sensor_time 与模型/迁移里的
  ix_sensor_data_sensor_id_recorded_at 完全相同（均在 (sensor_id, recorded_at) 上），
  是早期手工 DDL 遗留、已无任何代码引用的冗余索引。
  该表是全系统最高写入量的表，删除冗余索引可减少写放大与磁盘占用。
- 此处仅删“孤儿”索引，保留模型声明的 ix_sensor_data_sensor_id_recorded_at。
- DROP INDEX IF EXISTS 幂等且对普通（非唯一约束支撑）索引在 SQLite/PostgreSQL 均安全。

Revision ID: f0a1b2c3d4e5
Revises: e6f7a8b9c0d1
Create Date: 2026-08-24
"""
from typing import Sequence, Union

from alembic import op

revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_sensor_data_sensor_time")


def downgrade() -> None:
    op.execute(
        "CREATE INDEX idx_sensor_data_sensor_time ON sensor_data(sensor_id, recorded_at)"
    )
