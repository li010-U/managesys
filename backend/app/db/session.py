"""数据库会话管理"""
import logging

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings

logger = logging.getLogger("managesys.db")


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """启用 SQLite 优化配置"""
    cursor = dbapi_connection.cursor()
    # WAL 模式：支持并发读写
    cursor.execute("PRAGMA journal_mode=WAL")
    # 忙等待超时：避免并发时立即报错
    cursor.execute("PRAGMA busy_timeout=10000")
    # 同步模式 NORMAL：兼顾性能与安全
    cursor.execute("PRAGMA synchronous=NORMAL")
    # 外键约束
    cursor.execute("PRAGMA foreign_keys=ON")
    # 缓存大小提升至 64MB
    cursor.execute("PRAGMA cache_size=-64000")
    # 临时存储到内存
    cursor.execute("PRAGMA temp_store=MEMORY")
    # 内存映射 256MB
    cursor.execute("PRAGMA mmap_size=268435456")
    cursor.close()


# 创建引擎（使用配置中的连接池参数）
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    pool_recycle=settings.DB_POOL_RECYCLE,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
