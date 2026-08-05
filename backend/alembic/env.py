"""Alembic migration environment configuration (async-aware).

兼容 SQLite(aiosqlite) 与 PostgreSQL(asyncpg)：
使用与应用相同的异步 driver 运行在线迁移，无需额外安装同步驱动(如 psycopg2)。
"""
import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Alembic Config 对象
config = context.config

# 日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 导入所有模型
from app.db.base import Base  # noqa: E402
import app.models  # noqa: E402,F401

target_metadata = Base.metadata


def get_url() -> str:
    """优先使用环境变量 DATABASE_URL（与应用的异步 URL 一致），否则回退到 alembic.ini。"""
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return db_url
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """离线模式迁移"""
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """在线模式：使用异步引擎执行迁移。"""
    section = config.get_section(config.config_ini_section, {}) or {}
    connectable = async_engine_from_config(
        {**section, "sqlalchemy.url": get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
