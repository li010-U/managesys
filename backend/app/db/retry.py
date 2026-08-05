"""SQLite 并发写锁重试工具。

WAL 模式下并发写仍可能偶发 "database is locked"，busy_timeout 只能缓解。
本模块对提交/写事务提供带退避的自动重试，降低多人同时在线时 500 的概率。
"""
import asyncio
import logging
import weakref
from collections.abc import Awaitable, Callable
from typing import TypeVar

from sqlalchemy.exc import OperationalError

logger = logging.getLogger("managesys.db")

T = TypeVar("T")

# 需要重试的 SQLite 锁定错误关键字
_LOCK_KEYWORDS = (
    "database is locked",
    "database table is locked",
    "database schema is locked",
    "disk I/O error",
)

_DEFAULT_MAX_RETRIES = 3
_DEFAULT_DELAY = 0.05  # 初始延迟（秒），随后指数退避

# 进程内写锁：将同进程（同一事件循环）内的 SQLite 写操作（commit/flush）串行化，
# 从根源上消除“快速切换页面/多人同时在线”时同进程内的写锁竞争。
# asyncio.Lock 会绑定到首个使用它的事件循环，因此这里按事件循环懒创建，
# 避免在测试/重载等切换事件循环的场合报 “bound to a different event loop”。
_lock_by_loop = weakref.WeakKeyDictionary()


def _get_write_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = _lock_by_loop.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        _lock_by_loop[loop] = lock
    return lock


def _is_lock_error(exc: BaseException) -> bool:
    """判断异常是否为 SQLite 并发锁导致的错误。"""
    cursor = exc
    while cursor is not None:
        for kw in _LOCK_KEYWORDS:
            if kw in str(cursor).lower():
                return True
        if isinstance(cursor, OperationalError):
            pass
        cursor = getattr(cursor, "__cause__", None)
        if cursor is exc:
            break
    return False


async def with_commit_retry(
    operation: Callable[[], Awaitable[T]],
    max_retries: int = _DEFAULT_MAX_RETRIES,
    delay: float = _DEFAULT_DELAY,
) -> T:
    """带退避重试地执行写操作（如 commit/delete），应对 SQLite 并发锁。

    若连续重试仍失败则抛出最后一次异常。为了彻底避免同进程内并发写，
    这里先用进程内写锁将 commit/flush 串行化，再对偶发锁冲突做有限次重试。
    """
    # 串行化写，避免同一进程内的并发写锁冲突（快速切换页面/多人在线的常见诱因）
    async with _get_write_lock():
        attempt = 0
        while True:
            try:
                return await operation()
            except Exception as exc:  # noqa: BLE001
                if not _is_lock_error(exc) or attempt >= max_retries:
                    raise
                attempt += 1
                wait = delay * (2 ** (attempt - 1))
                logger.warning(
                    "SQLite 写锁冲突，第 %d/%d 次重试（等待 %.2fs）: %s",
                    attempt, max_retries, wait, exc,
                )
                await asyncio.sleep(wait)
