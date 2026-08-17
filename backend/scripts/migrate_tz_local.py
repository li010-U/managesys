#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""One-time migration: convert existing naive-UTC timestamps to local (Asia/Shanghai) time.
Run once with the app STOPPED. Back up the DB first.
Usage:  python scripts/migrate_tz_local.py [--db PATH] [--dry-run]
"""
import argparse
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import Base
from sqlalchemy import DateTime


def _discover_columns(conn):
    import app.models  # noqa: F401
    rows = []
    for table in Base.metadata.tables.values():
        exists = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table.name,)).fetchone()
        if not exists:
            continue
        cols = {r[1] for r in conn.execute("PRAGMA table_info(" + table.name + ")").fetchall()}
        for col in table.columns:
            if isinstance(col.type, DateTime) and col.name in cols:
                rows.append((table.name, col.name))
    return rows


def _parse(text):
    t = text.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(t, fmt), ("%Y-%m-%d %H:%M:%S.%f" if "%f" in fmt else "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    raise ValueError("unparsed: %r" % text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "managesys.db"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        print("DB not found:", db_path)
        sys.exit(1)

    import sqlite3
    conn = sqlite3.connect(db_path)
    total = 0
    try:
        cols = _discover_columns(conn)
        print("Found %d datetime columns to convert" % len(cols))
        for table, col in cols:
            rows = conn.execute("SELECT rowid, %s FROM %s WHERE %s IS NOT NULL" % (col, table, col)).fetchall()
            if not rows:
                continue
            n = 0
            for rowid, val in rows:
                dt, fmt = _parse(str(val))
                newdt = dt + timedelta(hours=8)
                newtxt = newdt.strftime(fmt)
                if not args.dry_run:
                    conn.execute("UPDATE %s SET %s = ? WHERE rowid = ?" % (table, col), (newtxt, rowid))
                total += 1
                n += 1
            if not args.dry_run:
                conn.commit()
            print("  %s.%s -> %d rows%s" % (table, col, n, " (dry)" if args.dry_run else ""))
        print("TOTAL rows touched:", total)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
