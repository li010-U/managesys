"""数据库写锁 / 提交重试工具测试。

覆盖：SQLite 并发写锁的识别、with_commit_retry 的退避重试，
以及进程内写锁对并发提交的串行化（防止快速切换/多人在线时写锁冲突）。
"""
import asyncio
import os
import tempfile

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.db.retry import with_commit_retry, _is_lock_error


def _locked_operational_error():
    """构造一个 SQLite "database is locked" 类型的错误。"""
    return OperationalError("UPDATE t SET x = 1", None, Exception("database is locked"))


class TestLockErrorDetection:
    """验证锁定错误识别。"""

    def test_detects_database_locked(self):
        assert _is_lock_error(_locked_operational_error()) is True

    def test_ignores_other_errors(self):
        assert _is_lock_error(ValueError("boom")) is False
        assert _is_lock_error(RuntimeError("database broken x")) is False


class TestCommitRetry:
    """验证 with_commit_retry 的退避重试行为。"""

    @pytest.mark.asyncio
    async def test_returns_operation_value(self):
        async def op():
            return 42

        assert await with_commit_retry(op, max_retries=1, delay=0) == 42

    @pytest.mark.asyncio
    async def test_retries_until_success(self):
        attempts = 0

        async def op():
            nonlocal attempts
            attempts += 1
            if attempts < 3:
                raise _locked_operational_error()
            return "ok"

        result = await with_commit_retry(op, max_retries=5, delay=0)
        assert result == "ok"
        assert attempts == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self):
        async def op():
            raise _locked_operational_error()

        with pytest.raises(OperationalError):
            await with_commit_retry(op, max_retries=2, delay=0)

    @pytest.mark.asyncio
    async def test_does_not_retry_non_lock_error(self):
        calls = 0

        async def op():
            nonlocal calls
            calls += 1
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await with_commit_retry(op, max_retries=5, delay=0)
        assert calls == 1


def _make_engine_and_session(db_path):
    """创建指向共享文件数据库的引擎与会话工厂。

    使用极小的 busy_timeout，便于在无写锁串行化时更容易触发 SQLite 锁定错误，
    从而让“写锁串行化”的效果更可被观测。
    """
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import event

    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine.sync_engine, "connect")
    def _set_pragma(dbapi_connection, _record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=50")
        cursor.close()

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, session_factory


class TestWriteLockSerialization:
    """验证进程内写锁能串行化并发提交，防止 SQLite 写锁冲突。"""

    @pytest.mark.asyncio
    async def test_concurrent_commits_no_lock_error_and_no_loss(self):
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "concurrent.db")
        try:
            engine, session_factory = _make_engine_and_session(db_path)

            async with engine.begin() as conn:
                await conn.execute(text(
                    "CREATE TABLE IF NOT EXISTS tick (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT)"
                ))

            total = 30

            async def worker(i):
                async with session_factory() as session:
                    async def commit():
                        await session.execute(text("INSERT INTO tick (v) VALUES (:v)"), {"v": f"w{i}"})
                        await session.commit()
                    # 所有并发写都通过进程内写锁串行化
                    await with_commit_retry(commit, max_retries=5, delay=0)

            await asyncio.gather(*[worker(i) for i in range(total)])

            async with engine.connect() as conn:
                count = (await conn.execute(text("SELECT COUNT(*) FROM tick"))).scalar()

            assert count == total, f"并发提交存在丢失: {count} != {total}"

            await engine.dispose()
        finally:
            # 清理临时文件
            for suffix in ("", "-wal", "-shm"):
                p = db_path + suffix
                if os.path.exists(p):
                    try:
                        os.remove(p)
                    except OSError:
                        pass
            try:
                os.rmdir(tmpdir)
            except OSError:
                pass


class TestWriteLockSerializationGuarantee:
    """验证进程内写锁确实把并发写操作串行化（同一时刻最多一个写操作）。

    这是对 with_commit_retry 所使用写锁的确定性回归测试：即便在单进程
    asyncio 事件循环里 SQLite 未必报锁错误，该锁也必须保证写操作不重叠。
    """

    @pytest.mark.asyncio
    async def test_operations_are_serialized(self):
        active = 0
        max_active = 0
        total = 20

        async def work():
            nonlocal active, max_active
            async def op():
                nonlocal active, max_active
                active += 1
                max_active = max(max_active, active)
                # 主动让出事件循环，若未加锁则此处会重叠
                await asyncio.sleep(0.001)
                active -= 1
            await with_commit_retry(op, max_retries=3, delay=0)

        await asyncio.gather(*[work() for _ in range(total)])

        assert max_active == 1, f"写操作未串行化，最大并发写数={max_active}"


class TestGetDbAutoCommitOnFlush:
    """验证修复后 get_db 会只要改写请求就提交，
    避免 "add+flush+refresh" 后寄生 new/dirty 为空导致写入被回滚。"""

    class _FakeRequest:
        method = "POST"

    @pytest.mark.asyncio
    async def test_flush_write_is_committed_on_mutating_method(self):
        from app.core.deps import get_db
        from app.models.role import Role
        from sqlalchemy import text

        code = "flush_test_%s" % id(object())
        gen = get_db(self._FakeRequest())
        db = await gen.__anext__()
        # 模拟服务层逻辑：add + flush + refresh 后不显式 commit
        role = Role(name=code, code=code, description="t")
        db.add(role)
        await db.flush()
        await db.refresh(role)
        # 此时 new/dirty/deleted 均为空，考验 get_db 是否仍会提交
        assert len(db.new) == 0 and len(db.dirty) == 0 and len(db.deleted) == 0
        # 恢复 generator 触发自动提交； generator 返回时会抛 StopAsyncIteration
        try:
            await gen.__anext__()
        except StopAsyncIteration:
            pass
        # 用新会话验证已持久化
        from app.db.session import async_session_factory
        async with async_session_factory() as check:
            res = await check.execute(text("SELECT COUNT(*) FROM roles WHERE code = :c"), {"c": code})
            assert res.scalar_one() == 1, "commit 后衬句 - flush 写入未持久化"
