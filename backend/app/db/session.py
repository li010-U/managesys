"""数据库会话管理"""
import logging

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.config import settings

logger = logging.getLogger("managesys.db")

# 判断当前使用哪个数据库方言
IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """启用 SQLite 优化配置（仅对 SQLite 生效）。"""
    # PostgreSQL 不存在 PRAGMA，直接跳过，避免连接建立失败。
    if not IS_SQLITE:
        return
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



# 连接池限制并发：
# - pool_size/max_overflow限制连接数上限，避免重压下连接无限增长。
# - pool_timeout等待空闲连接的最大时间，超时即报错，防止请求无限排队导致“加载不出来”。
# 创建引擎（使用配置中的连接池参数）
if IS_SQLITE:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=settings.DB_POOL_PRE_PING,
        pool_recycle=settings.DB_POOL_RECYCLE,
        connect_args={"check_same_thread": False},
    )
else:
    # PostgreSQL（asyncpg）：显式配置连接池，支撑多人同时在线。
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.DEBUG,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
        pool_pre_ping=settings.DB_POOL_PRE_PING,
        pool_recycle=settings.DB_POOL_RECYCLE,
        connect_args={"command_timeout": settings.DB_QUERY_TIMEOUT},
    )

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
