"""Pytest 配置和 fixtures"""
import pytest
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import tempfile

# 隔离测试环境：在导入 app.main / app.db.session 之前，把全局应用数据库
# 指向独立的临时 SQLite，避免任何测试触碰到线上 data/managesys.db。
# （app.main 及其依赖在首次 import 时即绑定引擎，故必须在导入前设置环境变量）
_tmp_db = tempfile.mktemp(prefix="pytest_app_", suffix=".db")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///" + _tmp_db)
os.environ.setdefault("DATABASE_URL_SYNC", "sqlite:///" + _tmp_db)
os.environ.setdefault("INIT_ADMIN_PASSWORD", "Pytest-Admin-12345")
os.environ.setdefault("SECRET_KEY", "pytest-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz-ABCDEFGHIJ")
os.environ.setdefault("DATA_RETENTION_TASK_ENABLED", "false")
os.environ.setdefault("ALERT_INTEL_TASK_ENABLED", "false")
os.environ.setdefault("ALERT_LIFECYCLE_TASK_ENABLED", "false")
os.environ.setdefault("ENV_POLL_TASK_ENABLED", "false")
os.environ.setdefault("ENABLE_CAPTCHA", "false")
os.environ.setdefault("REGISTER_ENABLED", "true")



@pytest.fixture(scope="function")
async def db_session():
    """创建测试数据库会话"""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from app.db.base import Base
    
    # 使用 SQLite 内存数据库进行测试
    from sqlalchemy import event as _sa_event
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )

    # 强制开启 SQLite 外键约束，与产线一致：
    # 这样测试才能真实验证模型里的 气联/级联/引用整体性约束，
    # 而不是被 SQLite 默认关闭外键而忽略。
    @_sa_event.listens_for(engine.sync_engine, "connect")
    def _enable_test_fk(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    
    # 创建表结构
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()
