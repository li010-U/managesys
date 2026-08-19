# -*- coding: utf-8 -*-
"""模型统一注册与 DB 表结构一致性回归测试。

背景：schema 由 Base.metadata 统一管理。若某模型类未被 models/__init__ 注册，
create_all/迁移就可能漏建表（历史教训：SensorAnomalyGap 曾未被导入、captcha_codes 是死表）。
本测试把「全部模型表都能被创建 + 关键表存在性/死表不存在」固化为回归断言。
"""
import pytest
from sqlalchemy import inspect

# 关键：先导入模型包，使所有模型类注册进 Base.metadata（与运行时 app.main 行为一致）。
import app.models  # noqa: F401


# 模型注册后应能访问到的全部表名（与 app/models 下各 __tablename__ 一致）
EXPECTED_TABLES = {
    "alert_actions", "alert_rules", "alerts",
    "audit_logs",
    "business_systems", "deployment_relations", "system_documents",
    "chat_conversations", "chat_messages",
    "device_lifecycles", "devices", "device_types",
    "env_weather_records", "transient_failure_events",
    "data_centers", "racks", "rooms",
    "inspection_issues", "inspection_plans", "inspection_records",
    "inspection_tasks", "inspection_templates",
    "ip_address_history", "ip_addresses", "ip_subnets",
    "kb_articles",
    "login_logs",
    "permissions", "role_permissions", "roles",
    "sensor_anomaly_gap", "sensor_data", "sensors",
    "user_roles", "users",
    "vlans",
    "work_order_attachments", "work_order_auto_rules",
    "work_order_categories", "work_order_comments", "work_orders",
}

# 已确认是死代码的模型表：不应被注册/创建
DEAD_TABLES = {"captcha_codes"}


@pytest.mark.asyncio
async def test_all_models_registered_and_creatable(db_session):
    """所有模型都应注册进 metadata 并能建表（防「漏建表/漏注册」）。"""
    from sqlalchemy import text
    from app.db.base import Base
    created = set((await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='table'")
    )).scalars().all())
    assert EXPECTED_TABLES <= created, f"漏建表: {EXPECTED_TABLES - created}"
    assert not (DEAD_TABLES & created), f"死表不应存在: {DEAD_TABLES & created}"
    # 模型数量与 metadata 表数量需与预期一致，防止新增模型未进 EXPECTED_TABLES
    metadata_tables = set(Base.metadata.tables.keys())
    assert EXPECTED_TABLES == metadata_tables, (
        f"EXPECTED_TABLES 与 metadata 不一致; 多出={metadata_tables - EXPECTED_TABLES}, 缺失={EXPECTED_TABLES - metadata_tables}"
    )


@pytest.mark.asyncio
async def test_sensor_anomaly_gap_registered(db_session):
    """SensorAnomalyGap 必须被注册（历史曾漏注册导致风险）。"""
    from app.db.base import Base
    assert "sensor_anomaly_gap" in Base.metadata.tables


# ???????/???????? __table_args__ ? alembic ???????
EXPECTED_INDEXES = {
    "ix_sensor_data_sensor_id_recorded_at",
    "ix_alerts_status_created_at",
    "ix_audit_logs_created_at",
    "ix_login_logs_created_at",
}


@pytest.mark.asyncio
async def test_hotpath_composite_indexes_present(db_session):
    """????????????/????????? create_all ??? schema?
    ???? __table_args__ ????/??/???????"""
    from sqlalchemy import text
    created = set((await db_session.execute(
        text("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'ix_%'")
    )).scalars().all())
    missing = EXPECTED_INDEXES - created
    assert not missing, f"???????: {missing}"
