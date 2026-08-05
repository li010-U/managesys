"""跨数据库方言的 SQL 辅助。

inspection/work_order 等接口使用原始 SQL，其写法（? 占位符、datetime('now')）
是 SQLite 风格，在 PostgreSQL 上无法直接运行。本模块提供：
  - q(sql, *params) : 把 SQLite 风格的 ? 占位符转换为 SQLAlchemy 命名绑定，
                      由 SQLAlchemy 按方言翻译为 ?（SQLite）或 $1（PostgreSQL）。
  - exec_sql(session, sql, params=()) : 便捷执行，参数为空则直接执行原始 SQL。
  同时约定时间使用标准 SQL 的 CURRENT_TIMESTAMP（SQLite 与 PostgreSQL 均支持）。
"""
import asyncio
import re

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from app.core.config import settings

_PLACEHOLDER = re.compile(r"\?")


def q(sql: str, *params) -> TextClause:
    """把 SQL 中的 ? 占位符替换为 :pN 并绑定参数。

    SQLAlchemy 在执行时会按当前方言把 :pN 翻译成合适的绑定样式，
    因此同一段 SQL 可同时用于 SQLite 与 PostgreSQL。
    """
    binds = {}
    counter = 0

    def replace(_match):
        nonlocal counter
        counter += 1
        name = f"p{counter}"
        if counter > len(params):
            raise ValueError(f"参数数量不足：SQL 有 {counter} 个 ?，仅提供 {len(params)} 个")
        binds[name] = params[counter - 1]
        return f":{name}"

    compiled = _PLACEHOLDER.sub(replace, sql)
    if counter < len(params):
        raise ValueError(f"参数过多：SQL 只有 {counter} 个 ?，却提供了 {len(params)} 个")
    return text(compiled).bindparams(**binds) if binds else text(sql)


async def exec_sql(session, sql: str, params=()):
    """按 SQLite 兼容方式执行原始 SQL；参数为空时直接执行，否则自动转换 ? 占位符。

    带单条 SQL 执行超时保护：超过 DB_QUERY_TIMEOUT 秒则抛出错误，
    避免查询悬置时请求长久排队导致“点快了加载不出来”。
    """
    async def _run():
        if params:
            return await session.execute(q(sql, *params))
        return await session.execute(text(sql))
    return await asyncio.wait_for(
        _run(),
        timeout=settings.DB_QUERY_TIMEOUT,
    )
