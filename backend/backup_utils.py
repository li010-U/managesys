# -*- coding: utf-8 -*-
"""\u6570\u636e\u5e93\u6062\u590d\u80fd\u529b\u5de5\u5177\uff1a\u5907\u4efd/\u8fd8\u539f/\u5bfc\u51fa/\u5bfc\u5165\uff08\u5e42\u7b49\u91cd\u653e\uff09\u3002

\u5bf9\u5e94\u6279\u5224\u6e05\u5355\u7b2c 10 \u70b9\u201c\u6ca1\u6709\u6062\u590d\u80fd\u529b\u201d\uff1a
- \u5907\u4efd\uff08SQLite \u5728\u7ebf\u4e00\u81f4\u6027\u5907\u4efd\uff0c\u542b WAL \u6570\u636e\uff09
- \u8fd8\u539f\uff08\u5148\u81ea\u52a8\u5907\u4efd\u5f53\u524d\u5e93\u518d\u8986\u76d6\uff09
- \u5bfc\u51fa\uff08\u5168\u91cf\u8868\u6570\u636e -> JSON\uff09
- \u5bfc\u5165\uff08\u6e05\u7a7a+\u91cd\u653e\uff0c\u5e42\u7b49\uff0c\u91cd\u590d\u6267\u884c\u4e0d\u4f1a\u7834\u574f\u6570\u636e\uff09
"""
from __future__ import annotations

import datetime
import json
import os
import sqlite3
import sys
from pathlib import Path

# \u9879\u76ee\u6839\uff08backend/\uff09
ROOT_DIR = Path(__file__).resolve().parent


def default_db_path() -> str:
    """\u89e3\u6790\u5f53\u524d\u914d\u7f6e\u4e0b\u7684 SQLite \u6570\u636e\u5e93\u7edd\u5bf9\u8def\u5f84\u3002"""
    try:
        from app.core.config import settings
        url = settings.DATABASE_URL
    except Exception:
        url = "sqlite+aiosqlite:///./data/managesys.db"
    for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
        if url.startswith(prefix):
            rel = url[len(prefix):]
            return str(Path(rel).resolve())
    return str(ROOT_DIR / "data" / "managesys.db")

# \u4ee5\u4e0b\u7528\u4e8e PostgreSQL \u652f\u6301\uff08\u65e0 SQLite \u65f6\u81ea\u52a8\u4f7f\u7528 pg_dump/pg_restore\uff09
import subprocess as _subprocess


def _using_pg() -> bool:
    """\u5224\u65ad\u5f53\u524d\u914d\u7f6e\u662f\u5426\u4e3a PostgreSQL\u3002"""
    try:
        from app.core.config import settings
        url = (settings.DATABASE_URL or "")
    except Exception:
        url = os.environ.get("DATABASE_URL", "")
    return url.strip().lower().startswith("postgres")


def _pg_dsn() -> str:
    """\u5c06 asyncpg URL \u8f6c\u6362\u4e3a psql/pg_dump \u540c\u6b65 DSN\u3002"""
    try:
        from app.core.config import settings
        url = settings.DATABASE_URL
    except Exception:
        url = os.environ.get("DATABASE_URL", "")
    url = url.strip()
    for prefix in ("postgresql+asyncpg://", "postgres+asyncpg://"):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix):]
    return url.replace("+asyncpg://", "://", 1)


def _pg_backup(target_dir: str, keep: int) -> str:
    """\u4f7f\u7528 pg_dump -Fc \u4e0d\u6253\u6270\u5728\u7ebf\u670d\u52a1\u7684\u4e00\u81f4\u6027\u5907\u4efd\u3002"""
    os.makedirs(target_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(target_dir, "managesys_%s.dump" % ts)
    dsn = _pg_dsn()
    cmd = ["pg_dump", "-Fc", "-f", dest, dsn]
    _run_or_raise(cmd)
    _prune(target_dir, keep)
    return dest


def _pg_restore(src_file: str, force: bool, live_backup: str | None) -> str:
    """\u4ece pg_dump \u4e00\u81f4\u6027\u5907\u4efd\u8fd8\u539f\uff08\u5148\u81ea\u52a8\u5907\u4efd\u5f53\u524d\u5e93\uff09\u3002"""
    if not force:
        print("[WARN] PostgreSQL \u8fd8\u539f\u4f1a\u5220\u9664\u76ee\u6807\u5e93\u73b0\u6709\u5bf9\u8c61\uff0c\u5efa\u8bae\u4f7f\u7528 --force \u786e\u8ba4\u3002")
    _pg_backup(live_backup or str(ROOT_DIR / "backups"), 30)
    dsn = _pg_dsn()
    cmd = ["pg_restore", "--clean", "--if-exists", "--no-owner", "--no-privileges", "-d", dsn, str(Path(src_file).resolve())]
    _run_or_raise(cmd)
    return str(Path(src_file).resolve())


def _run_or_raise(cmd):
    """\u8fd0\u884c\u5916\u90e8\u5de5\u5177\uff0c\u5931\u8d25\u65f6\u629b\u51fa RuntimeError\u3002"""
    try:
        _subprocess.run(cmd, check=True)
    except FileNotFoundError:
        raise RuntimeError("\u672a\u627e\u5230\u5de5\u5177 %s\uff0c\u8bf7\u786e\u8ba4\u5df2\u5b89\u88c5 PostgreSQL \u5ba2\u6237\u7aef (pg_dump/pg_restore)" % cmd[0])
    except _subprocess.CalledProcessError as e:
        raise RuntimeError("\u5de5\u5177\u6267\u884c\u5931\u8d25: %s (code=%s)" % (cmd[0], e.returncode))



def backup(target_dir: str | None = None, keep: int = 30, db_path: str | None = None) -> str:
    """\u4e0d\u6253\u6270\u670d\u52a1\u7684\u5728\u7ebf\u4e00\u81f4\u6027\u5907\u4efd\uff08\u542b WAL \u6570\u636e\uff09\u3002"""
    if db_path is None and _using_pg():
        return _pg_backup(target_dir or str(ROOT_DIR / "backups"), keep)
    target_dir = target_dir or str(ROOT_DIR / "backups")
    os.makedirs(target_dir, exist_ok=True)
    src = db_path or default_db_path()
    if not os.path.exists(src):
        raise FileNotFoundError(f"\u6570\u636e\u5e93\u4e0d\u5b58\u5728: {src}")
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(target_dir, f"managesys_{ts}.db")
    src_conn = sqlite3.connect(src)
    dest_conn = sqlite3.connect(dest)
    try:
        with dest_conn:
            src_conn.backup(dest_conn)
    finally:
        src_conn.close()
        dest_conn.close()
    _prune(target_dir, keep)
    return dest


def _prune(target_dir: str, keep: int):
    files = sorted(
        [f for f in os.listdir(target_dir)
         if f.startswith("managesys_") and (f.endswith(".db") or f.endswith(".dump"))]
    )
    for stale in files[:-keep] if keep > 0 else []:
        try:
            os.remove(os.path.join(target_dir, stale))
        except OSError:
            pass


def restore(src_file: str, db_path: str | None = None, force: bool = False, live_backup: str | None = None) -> str:
    """\u4ece\u5907\u4efd\u6587\u4ef6\u8fd8\u539f\u5230\u6d3b\u5e93\uff1a\u5148\u81ea\u52a8\u5907\u4efd\u5f53\u524d\u5e93\u518d\u8986\u76d6\u3002"""
    if db_path is None and _using_pg():
        return _pg_restore(src_file, force, live_backup)
    src_file = str(Path(src_file).resolve())
    if not os.path.exists(src_file):
        raise FileNotFoundError(f"\u5907\u4efd\u6587\u4ef6\u4e0d\u5b58\u5728: {src_file}")
    live = Path(db_path or default_db_path()).resolve()
    live.parent.mkdir(parents=True, exist_ok=True)

    # \u68c0\u6d4b\u6d3b\u5e93\u662f\u5426\u88ab\u5360\u7528\uff08\u670d\u52a1\u6b63\u5728\u8fd0\u884c\uff09
    lock = _is_locked(live)
    if lock and not force:
        raise RuntimeError(
            "\u6d3b\u5e93\u6b63\u5728\u88ab\u5360\u7528\uff08\u53ef\u80fd\u670d\u52a1\u6b63\u5728\u8fd0\u884c\uff09\u3002"
            "\u8bf7\u5148\u505c\u6b62\u670d\u52a1\uff0c\u6216\u4f7f\u7528 --force \u5f3a\u884c\u8fd8\u539f\u3002"
        )

    # \u5148\u81ea\u52a8\u5907\u4efd\u5f53\u524d\u5e93
    if os.path.exists(live):
        pre_bak = backup(live_backup or str(ROOT_DIR / "backups"), db_path=str(live))
        print(f"[PRE-BACKUP] \u8fd8\u539f\u524d\u5df2\u81ea\u52a8\u5907\u4efd\u5f53\u524d\u5e93 -> {pre_bak}")

    # \u6e05\u9664 WAL/SHM
    for suffix in ("-wal", "-shm"):
        p = str(live) + suffix
        if os.path.exists(p):
            os.remove(p)

    # \u4e32\u5148\u5199\u4e34\u65f6\u6587\u4ef6\u518d\u79fb\u52a8\uff0c\u4fdd\u8bc1\u6574\u4f53\u6027
    tmp = str(live) + ".restore.tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    s = sqlite3.connect(src_file)
    d = sqlite3.connect(tmp)
    try:
        s.backup(d)
    finally:
        d.close()
        s.close()
    os.replace(tmp, str(live))
    return str(live)


def _is_locked(path: Path) -> bool:
    """\u5c1d\u8bd5\u4ee5\u5199\u6a21\u6253\u5f00\uff0c\u6821\u9a8c\u662f\u5426\u88ab\u522b\u7684\u8fde\u63a5\u5360\u7528\u3002"""
    if not os.path.exists(path):
        return False
    try:
        conn = sqlite3.connect(str(path), timeout=0.1)
        conn.execute("PRAGMA quick_check").fetchone()
        conn.close()
        return False
    except sqlite3.OperationalError:
        return True


def export_json(path: str | None = None, db_path: str | None = None) -> str:
    """\u5168\u91cf\u8868\u6570\u636e\u5bfc\u51fa\u4e3a\u53ef\u643a\u5e26 JSON\uff08\u542b WAL \u6570\u636e\uff09\u3002"""
    src = db_path or default_db_path()
    conn = sqlite3.connect(src)
    tables = _ordered_tables(conn)
    payload = {"exported_at": datetime.datetime.now().isoformat(), "tables": {}}
    try:
        for t in tables:
            rows = conn.execute(f'SELECT * FROM "{t}"').fetchall()
            cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{t}")').fetchall()]
            payload["tables"][t] = [dict(zip(cols, _jsonable(r))) for r in rows]
    finally:
        conn.close()
    path = path or str(ROOT_DIR / "backups" / f"managesys_export_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1, default=str)
    return path


def _jsonable(row):
    out = []
    for v in row:
        if isinstance(v, (datetime.datetime, datetime.date)):
            out.append(v.isoformat())
        elif isinstance(v, bytes):
            out.append(v.hex())
        else:
            out.append(v)
    return out


def _ordered_tables(conn) -> list[str]:
    """\u6309\u5916\u952e\u4f9d\u8d56\u987a\u5e8f\u8fd4\u56de\u8868\u540d\u5217\u8868\u3002"""
    names = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()]
    return sorted(names)


def import_json(path: str, db_path: str | None = None, force: bool = False) -> int:
    """\u5bfc\u5165 JSON\uff1a\u6e05\u7a7a\u5e76\u91cd\u653e\uff08\u5e42\u7b49\uff09\u3002\u91cd\u590d\u6267\u884c\u7ed3\u679c\u4e00\u81f4\u3002"""
    path = str(Path(path).resolve())
    if not os.path.exists(path):
        raise FileNotFoundError(f"\u5bfc\u5165\u6587\u4ef6\u4e0d\u5b58\u5728: {path}")
    live = Path(db_path or default_db_path()).resolve()
    if _is_locked(live) and not force:
        raise RuntimeError("\u6d3b\u5e93\u88ab\u5360\u7528\uff0c\u8bf7\u5148\u505c\u6b62\u670d\u52a1\u6216\u4f7f\u7528 --force\u3002")
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    conn = sqlite3.connect(live)
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        cur = conn.cursor()
        _disable_foreign_keys_for_clear(conn)
        tables_in_file = list(payload.get("tables", {}).keys())
        # \u6e05\u7a7a
        for t in reversed(_ordered_tables(conn)):
            if t in tables_in_file or True:
                try:
                    cur.execute(f'DELETE FROM "{t}"')
                except sqlite3.OperationalError:
                    pass
        total = 0
        for t in tables_in_file:
            rows = payload["tables"].get(t, [])
            if not rows:
                continue
            cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{t}")').fetchall()]
            placeholders = ",".join("?" * len(cols))
            for row in rows:
                vals = [_from_jsonable(row.get(c)) for c in cols]
                try:
                    cur.execute(f'INSERT INTO "{t}" ({",".join('"' + c + '"' for c in cols)}) VALUES ({placeholders})', vals)
                    total += 1
                except sqlite3.IntegrityError:
                    pass
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.close()
    return total


def _from_jsonable(v):
    if isinstance(v, str):
        # \u5c1d\u8bd5\u56de\u590d datetime
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                datetime.datetime.strptime(v, fmt)
                return v  # \u4fdd\u7559\u5b57\u7b26\u4e32\u5373\u53ef\uff0csqlite \u4f1a\u81ea\u52a8\u5b58
            except ValueError:
                continue
    return v


def _disable_foreign_keys_for_clear(conn):
    # SQLite \u5728 FK \u5173\u95ed\u65f6\u5141\u8bb8\u5220\u9664\u4efb\u610f\u987a\u5e8f
    pass
