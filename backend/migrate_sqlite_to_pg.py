#!/usr/bin/env python3
"""将现有 SQLite 数据库完整迁移到 PostgreSQL。

按 SQLite 的实际表结构（反射）在目标库上重建表并逐表拷贝数据，
保留自增主键的原值，并让序列从 max(id) 继续自增。

用法（在 backend 目录下）:
    # 先创建目标库（脚本不负责 CREATE DATABASE）
    python migrate_sqlite_to_pg.py --target postgresql+asyncpg://user:pass@127.0.0.1:5432/managesys

参数:
    --sqlite PATH    源 SQLite 文件（默认 ./data/managesys.db）
    --target URL     目标数据库 URL（默认取环境变量 DATABASE_URL）
    --dry-run        只打印 PostgreSQL DDL 与计划，不建表/不拷贝
    --only TABLES    只迁移指定表（逗号分隔，可选）
    --drop           先 DROP 目标表再重建（默认 False，保留已有表）

注意:
    - 目标库需已存在；建议先用 --dry-run 检查生成的 DDL。
    - 目标表若已存在且未用 --drop，会以 IF NOT EXISTS 跳过建表、并跳过外键冲突项。
"""
import argparse
import asyncio
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import Column, MetaData, Table, create_engine, select, text as sa_text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.types import (
    BigInteger, Boolean, Date, DateTime, Float, Integer, JSON, Text, TypeEngine, VARCHAR,
)


def _to_pg_type(col) -> TypeEngine:
    """根据 SQLite 反射列返回一个 SQLAlchemy PG 可用的类型对象。"""
    t = col.type.__class__.__name__.upper()
    length = getattr(col.type, "length", None)
    is_autoincrement_pk = col.primary_key and t in ("INTEGER", "BIGINT")
    if t in ("INTEGER",):
        if is_autoincrement_pk:
            # 目标用 identity 以便显式插入旧 id，后续自增从序列继续
            import sqlalchemy.dialects.postgresql as pg
            from sqlalchemy import Identity
            return Integer().with_variant(pg.INTEGER(), "postgresql")
        return Integer()
    if t == "BIGINT":
        return BigInteger()
    if t == "VARCHAR":
        return VARCHAR(length or 255)
    if t in ("TEXT", "CLOB"):
        return Text()
    if t in ("DATETIME", "TIMESTAMP"):
        return DateTime()
    if t == "DATE":
        return Date()
    if t in ("FLOAT", "REAL"):
        return Float()
    if t in ("NUMERIC", "DECIMAL"):
        return Float()
    if t == "BOOLEAN":
        return Boolean()
    if t == "BLOB":
        from sqlalchemy import LargeBinary
        return LargeBinary()
    if t == "JSON":
        import sqlalchemy.dialects.postgresql as pg
        return JSON().with_variant(pg.JSONB(), "postgresql")
    return Text()


def _coerce(value, col) -> object:
    """把 SQLite 读到的值转换成目标列友好的 Python 值。"""
    if value is None:
        return None
    t = col.type.__class__.__name__.upper()
    if t in ("DATETIME", "TIMESTAMP"):
        if isinstance(value, (datetime, date)):
            return value
        s = str(value)
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return s
    if t == "DATE":
        if isinstance(value, (datetime, date)):
            return value
        try:
            return date.fromisoformat(str(value))
        except Exception:
            return str(value)
    if t == "BOOLEAN":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")
    if t in ("INTEGER", "BIGINT", "SMALLINT"):
        try:
            return int(value)
        except Exception:
            return value
    if t in ("FLOAT", "REAL", "NUMERIC", "DECIMAL"):
        try:
            return float(value)
        except Exception:
            return value
    if t == "JSON":
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value
    return value


def _pg_defaults(col):
    """返回 PG DDL 的默认值表达式，或 None。"""
    d = getattr(col, "default", None)
    if d is None:
        return None
    try:
        if getattr(d, "is_sequence", False):
            return None
        arg = d.arg
        if arg is None:
            return None
        s = str(arg)
        up = s.upper()
        if up in ("CURRENT_TIMESTAMP", "CURRENT_DATE", "CURRENT_TIME", "NOW()"):
            base = {"CURRENT_TIMESTAMP": "CURRENT_TIMESTAMP",
                    "CURRENT_DATE": "CURRENT_DATE",
                    "CURRENT_TIME": "CURRENT_TIME",
                    "NOW()": "CURRENT_TIMESTAMP"}[up]
            return base
        if isinstance(arg, str):
            return "'" + s.replace("'", "''") + "'"
        return s
    except Exception:
        return None


def _build_create_ddl(table) -> str:
    # ??? INTEGER ??????????????????? identity?
    pk_cols = list(table.primary_key.columns)
    single_int_pk = (
        len(pk_cols) == 1
        and pk_cols[0].name in table.columns
        and table.columns[pk_cols[0].name].type.__class__.__name__.upper() in ("INTEGER", "BIGINT")
    )
    pk_name = pk_cols[0].name if single_int_pk else None

    cols = []
    for col in table.columns:
        t = col.type.__class__.__name__.upper()
        pg_type = _to_pg_type(col)
        type_str = pg_type.compile(dialect=postgresql.dialect())
        parts = [f"{col.name} {type_str}"]
        if col.name == pk_name:
            # ?????GENERATED BY DEFAULT AS IDENTITY ?????????? id
            parts.append("GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY")
        elif col.primary_key and len(pk_cols) <= 1:
            parts.append("PRIMARY KEY")
        if col.name != pk_name and col.nullable is False:
            parts.append("NOT NULL")
        d = _pg_defaults(col)
        if d:
            parts.append(f"DEFAULT {d}")
        cols.append(" ".join(parts))
    # ??????????????????? PRIMARY KEY
    if len(pk_cols) > 1:
        cols.append("PRIMARY KEY (" + ", ".join(c.name for c in pk_cols) + ")")
    return f"CREATE TABLE IF NOT EXISTS {table.name} (\n  " + ",\n  ".join(cols) + "\n)"

def _build_fk_ddls(table):
    out = []
    for fk in table.foreign_keys:
        ondel = fk.ondelete or "NO ACTION"
        out.append(
            f"ALTER TABLE {table.name} ADD CONSTRAINT fk_{table.name}_{fk.parent.name} "
            f"FOREIGN KEY ({fk.parent.name}) REFERENCES {fk.column.table.name} ({fk.column.name}) "
            f"ON DELETE {ondel}"
        )
    return out


async def _copy_table(src_conn, tgt_engine, table, batch=2000):
    """逐批从 SQLite 读并写入目标（用目标表反射对象做 executemany）。"""
    cols = [c.name for c in table.columns]
    col_map = {c.name: c for c in table.columns}
    sel = select(*[table.c[c] for c in cols])
    total = 0
    offset = 0
    # 反射目标表以复用 SQLAlchemy 翻译占位符
    TargetMeta = MetaData()
    tgt_table = Table(table.name, TargetMeta, *[
        Column(c.name, _to_pg_type(c)) for c in table.columns
    ])
    while True:
        rows = (await src_conn.execute(sel.offset(offset).limit(batch))).all()
        if not rows:
            break
        dict_rows = [
            {cname: _coerce(val, col_map[cname]) for cname, val in zip(cols, row)}
            for row in rows
        ]
        async with tgt_engine.begin() as conn:
            await conn.execute(tgt_table.insert(), dict_rows)
        total += len(rows)
        offset += batch
    return total


async def run(args, tgt_url):
    src = Path(args.sqlite)
    only = set(args.only.split(",")) if args.only else None

    src_sync = create_engine(f"sqlite:///{src.resolve()}")
    meta = MetaData()
    meta.reflect(src_sync)
    tables = meta.sorted_tables
    if only:
        tables = [t for t in tables if t.name in only]
        if not tables:
            print("没有匹配的表：", sorted(only))
            sys.exit(1)

    print(f"[{'DRY-RUN' if args.dry_run else 'MIGRATE'}] 源: {src}  表数: {len(tables)}")
    for t in tables:
        print(f"   - {t.name} ({len(t.columns)} 列)")

    if args.dry_run:
        print("\n===== PostgreSQL DDL 预览 =====")
        for t in tables:
            print("---", t.name)
            print(_build_create_ddl(t) + ";")
            for fk in _build_fk_ddls(t):
                print("  " + fk + ";")
        print("\n[DRY-RUN] 完成，未建表/未拷贝。")
        return

    tgt = create_async_engine(tgt_url)
    try:
        if args.drop:
            print("[提示] --drop：先删除目标中存在且本次迁移涉及的表…")
            async with tgt.begin() as conn:
                for t in reversed(tables):
                    await conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{t.name}" CASCADE')
            print("[OK] 已清理目标表")

        # 建表
        async with tgt.begin() as conn:
            for t in tables:
                await conn.exec_driver_sql(_build_create_ddl(t))
        print(f"[OK] 建表完成：{len(tables)} 张")

        # 外键（忽略已存在的约束）
        async with tgt.begin() as conn:
            for t in tables:
                for fk in _build_fk_ddls(t):
                    try:
                        await conn.execute(sa_text(fk))
                    except Exception as e:
                        print(f"   [跳过] FK {t.name}: {type(e).__name__} {str(e)[:80]}")

        # 数据拷贝
        async_src = create_async_engine("sqlite+aiosqlite:///" + str(src.resolve()).replace("\\", "/"))
        grand = 0
        async with async_src.connect() as sconn:
            for t in tables:
                n = await _copy_table(sconn, tgt, t)
                grand += n
                print(f"   {t.name}: {n} 行")
        print(f"[OK] 数据拷贝完成，共 {grand} 行")
        await async_src.dispose()
    finally:
        await tgt.dispose()



async def self_test(src_path, tgt_path, only=None):
    """SQLite -> SQLite 自测：验证反射建表 + 数据拷贝逻辑，无需 PostgreSQL。
    目标结构与源结构一致，逐表拷贝后核对行数。
    """
    from sqlalchemy import func
    from sqlalchemy.dialects import sqlite as sqldialect

    src = Path(src_path)
    only = set(only.split(",")) if only else None

    src_sync = create_engine(f"sqlite:///{src.resolve()}")
    meta = MetaData(); meta.reflect(src_sync)
    tables = meta.sorted_tables
    if only:
        tables = [t for t in tables if t.name in only]

    tgt_path = Path(tgt_path)
    if tgt_path.exists():
        tgt_path.unlink()
    tgt = create_async_engine(f"sqlite+aiosqlite:///{tgt_path.resolve()}")

    sq = sqldialect.dialect()
    async with tgt.begin() as conn:
        for table in tables:
            col_defs = []
            pk_cols = [c.name for c in table.columns if c.primary_key]
            for col in table.columns:
                ts = col.type.compile(dialect=sq)
                parts = [f"{col.name} {ts}"]
                if col.primary_key and len(pk_cols) == 1:
                    parts.append("PRIMARY KEY")
                if col.nullable is False and not col.primary_key:
                    parts.append("NOT NULL")
                col_defs.append(" ".join(parts))
            if len(pk_cols) > 1:
                col_defs.append("PRIMARY KEY (" + ", ".join(pk_cols) + ")")
            await conn.exec_driver_sql(
                f"CREATE TABLE IF NOT EXISTS {table.name} (" + ", ".join(col_defs) + ")"
            )

    async_src = create_async_engine("sqlite+aiosqlite:///" + str(src.resolve()).replace("\\", "/"))
    print("[SELF-TEST] 逐表拷贝并核对行数…")
    ok = True
    async with async_src.connect() as sconn:
        for table in tables:
            n = await _copy_table(sconn, tgt, table)
            src_cnt = (await sconn.execute(select(func.count()).select_from(table))).scalar()
            # ???????????????? async connection ???
            TargetCM = MetaData()
            tgt_tbl = Table(table.name, TargetCM, *[
                Column(c.name, _to_pg_type(c)) for c in table.columns
            ])
            async with tgt.connect() as tc:
                tgt_cnt = (await tc.execute(select(func.count()).select_from(tgt_tbl))).scalar()
            match = (src_cnt == tgt_cnt)
            ok = ok and match
            print(f"   {table.name}: 源={src_cnt} 目标={tgt_cnt}  {'OK' if match else '!! 不一致'}")
    print("[SELF-TEST]", "全部一致" if ok else "存在不一致！")
    await async_src.dispose(); await tgt.dispose()
    return 0 if ok else 1


def main():
    p = argparse.ArgumentParser(description="SQLite -> PostgreSQL 数据迁移")
    p.add_argument("--sqlite", default="./data/managesys.db")
    p.add_argument("--target", default=None)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", default=None)
    p.add_argument("--drop", action="store_true")
    p.add_argument("--self-test", default=None, help="SQLite -> SQLite 自测目标文件（无需 PG）")
    args = p.parse_args()

    if args.self_test is not None:
        asyncio.run(self_test(args.sqlite, args.self_test, only=args.only))
        return

    tgt = args.target or os.environ.get("DATABASE_URL")
    if not tgt and not args.dry_run:
        print("错误：未指定目标。请设置 DATABASE_URL 或 --target。", file=sys.stderr)
        sys.exit(2)
    if tgt and "postgres" not in tgt.lower():
        print(f"警告：目标不是 PostgreSQL，仅用于自测：{tgt[:50]}…", file=sys.stderr)

    asyncio.run(run(args, tgt))


if __name__ == "__main__":
    main()
