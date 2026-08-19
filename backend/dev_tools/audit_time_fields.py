# -*- coding: utf-8 -*-
"""只读审计：清点系统内各时间字段的写入口径，输出取时方式清单。

不修改任何数据/文件。扫描 app 下所有 .py，识别三类取时方式：
  - SQL 层:  datetime('now','localtime') / CURRENT_TIMESTAMP
  - Python 层: datetime.now()  (本地 naive)
  - 协议层:   datetime.now(timezone.utc) / utcnow()   (aware UTC，仅应用于 JWT)
同时读取 SQLite 库做抽样交叉核验（不写库）。
"""
from __future__ import annotations

import os
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
DB_PATH = Path(__file__).resolve().parents[1] / "data" / "managesys.db"

RE_SQL_LOCAL = re.compile(r"datetime\(\s*'now'\s*,\s*'localtime'\s*\)")
RE_SQL_UTC_TS = re.compile(r"CURRENT_TIMESTAMP\b")
RE_PY_NOW = re.compile(r"datetime\.now\(\)")
RE_PY_NOW_ARGS = re.compile(r"datetime\.now\s*\([^)]*\)")
RE_UTCNOW = re.compile(r"\butcnow\s*\(")
RE_PY_UTC = re.compile(r"datetime\.now\s*\(\s*timezone\.utc\s*\)")


def _classify_line(line: str) -> set[str]:
    kinds = set()
    if RE_SQL_LOCAL.search(line):
        kinds.add("sql:datetime('now','localtime')")
    if RE_SQL_UTC_TS.search(line):
        kinds.add("sql:CURRENT_TIMESTAMP")
    if RE_UTCNOW.search(line) or RE_PY_UTC.search(line):
        kinds.add("py:utcnow(UTC aware)")
    if RE_PY_NOW.search(line):
        kinds.add("py:datetime.now()")
    return kinds


def scan_source() -> dict:
    by_file: dict[str, list[tuple[int, str]]] = defaultdict(list)
    totals = defaultdict(int)
    for py in sorted(APP_DIR.rglob("*.py")):
        rel = py.relative_to(APP_DIR)
        try:
            lines = py.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        for idx, line in enumerate(lines, 1):
            kinds = _classify_line(line)
            if not kinds:
                continue
            kinds_s = ",".join(sorted(kinds))
            by_file[str(rel)].append((idx, kinds_s))
            for k in kinds:
                totals[k] += 1
    return by_file, totals


def probe_db() -> dict:
    """/只读/ 抽样核验各表时间字段的取值口径特征：精度、created_at==updated_at 比例、未来时间等。"""
    out = {}
    if not DB_PATH.exists():
        return {"error": f"db not found: {DB_PATH}"}
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in c.fetchall()]
    for t in sorted(tables):
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({t})")]
        tcols = [x for x in cols if "time" in x.lower() or "at" in x.lower() or x == "start_time" or x == "end_time"]
        rec = {"time_cols": tcols}
        if "created_at" in cols and "updated_at" in cols:
            try:
                tot, same = c.execute(f"SELECT COUNT(*), SUM(created_at==updated_at) FROM {t}").fetchone()
                rec["total"] = tot
                rec["created_eq_updated"] = int(same or 0)
            except Exception:
                pass
        if "created_at" in cols:
            try:
                row = c.execute(
                    f"SELECT COUNT(*), MIN(created_at), MAX(created_at), COUNT(DISTINCT created_at) FROM {t}"
                ).fetchone()
                rec["created_min"], rec["created_max"] = row[1], row[2]
                rec["created_distinct"] = row[3]
            except Exception:
                pass
        if tcols:
            out[t] = rec
    conn.close()
    return out


def print_db_report(probe: dict) -> None:
    print("\n========== [A] 数据库时间字段抽样核验(只读) ==========")
    for t, rec in probe.items():
        print(f"\n-- {t} --")
        print("   时间列:", rec.get("time_cols"))
        if rec.get("total") is not None:
            print(f"   total={rec['total']}  created_at==updated_at={rec.get('created_eq_updated')} "
                  f"created_at_distinct={rec.get('created_distinct')}")
        if rec.get("created_min"):
            print(f"   created_at range: {rec.get('created_min')} ~ {rec.get('created_max')}")


def print_source_report(by_file: dict, totals: dict) -> None:
    print("\n========== [B] 源码取时方式清单(只读) ==========")
    print("各类取时方式出现次数:")
    for k in sorted(totals):
        print(f"   {totals[k]:4d}  {k}")
    print("\n未使用 timeutil.now_local() 的散落写法（按文件）:")
    for rel, hits in sorted(by_file.items()):
        for lineno, kinds in hits:
            print(f"   {rel}:{lineno}  [{kinds}]")


if __name__ == "__main__":
    print("启动只读审计 audit_time_fields.py ...")
    print(f"源码目录: {APP_DIR}")
    print(f"数据库(只读): {DB_PATH}")
    by_file, totals = scan_source()
    probe = probe_db()
    print_db_report(probe)
    print_source_report(by_file, totals)
