# -*- coding: utf-8 -*-
"""数据一致性体检工具：检查并报告孤儿设备 / U 位叠加 / 超限 /
IP 重复登记 / 未挂机柜设备 / 机柜 3D 布局等。同时支持 SQLite 与 PostgreSQL
（数据库来源由 DATABASE_URL 决定）。

用法:
    python manage.py check-data                 # 仅报告
    python manage.py check-data --fix           # 报告 + 安全自动修复
    python manage.py check-data --db <path>     # 指定 SQLite 库文件
"""
from __future__ import annotations
import asyncio
import os
from collections import defaultdict
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parent

DEFAULT_DB = str(ROOT / "data" / "managesys.db")


def resolve_db_url(db_path: str | None = None) -> str:
    def _file_to_url(p: str) -> str:
        return "sqlite+aiosqlite:///" + str(Path(p).resolve()).replace("\\", "/")

    if db_path:
        low = db_path.strip().lower()
        if low.startswith(("sqlite", "postgres")):
            return db_path.strip()
        return _file_to_url(db_path)

    env = (os.environ.get("DATABASE_URL") or "").strip()
    if env:
        if env.startswith("sqlite:///"):
            p = env.split("///", 1)[-1]
            if not p:
                return _file_to_url(DEFAULT_DB)
            pp = Path(p)
            if not pp.is_absolute():
                pp = ROOT / pp
            return "sqlite+aiosqlite:///" + str(pp.resolve()).replace("\\", "/")
        return env
    return _file_to_url(DEFAULT_DB)


def _label(db_path: str | None = None) -> str:
    return resolve_db_url(db_path)


async def _rows(conn, sql, **params):
    return (await conn.execute(text(sql), params)).mappings().all()


async def _scalar(conn, sql, **params):
    return (await conn.execute(text(sql), params)).scalar()


def _run(coro):
    return asyncio.run(coro)


def run_audit(db: str | None = None) -> dict:
    url = resolve_db_url(db)
    report = {"db": _label(db), "sections": {}, "summary": {"ok": 0, "warn": 0, "error": 0}}
    return _run(_audit_core(url, report))


async def _audit_core(url, report):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            await _audit_orphan_devices(conn, report)
            await _audit_u_positions(conn, report)
            await _audit_rack_units(conn, report)
            await _audit_rack_layout(conn, report)
            await _audit_ip_ledger(conn, report)
            await _audit_referential(conn, report)
    finally:
        await engine.dispose()
    report["summary"]["total_findings"] = sum(report["summary"].values())
    return report


def _add(report, section, level, msg):
    report["sections"].setdefault(section, []).append({"level": level, "msg": msg, "count": 0})
    report["summary"][level if level in report["summary"] else "warn"] += 1


async def _audit_orphan_devices(conn, report):
    sec = "orphan_devices"
    orphan = await _rows(
        conn,
        "SELECT d.id, d.name, d.status FROM devices d "
        "WHERE d.rack_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM racks r WHERE r.id=d.rack_id)",
    )
    for r in orphan:
        _add(report, sec, "error", "设备 #%s %s (status=%s) 挂了不存在的机柜 rack_id" % (r["id"], r["name"], r["status"]))
    unmounted = await _scalar(conn, "SELECT COUNT(*) FROM devices WHERE rack_id IS NULL")
    if unmounted:
        report.setdefault("info_counts", {})["unmounted_devices"] = unmounted
    if not orphan:
        report["sections"][sec] = report["sections"].get(sec, [])
        report["summary"]["ok"] += 1


async def _audit_u_positions(conn, report):
    sec = "u_positions"
    devs = await _rows(
        conn,
        "SELECT d.id, d.name, d.rack_id, d.start_u, d.end_u, r.total_units "
        "FROM devices d JOIN racks r ON d.rack_id=r.id WHERE d.rack_id IS NOT NULL",
    )
    by_rack = defaultdict(list)
    for d in devs:
        s, e = d["start_u"], d["end_u"]
        if s is None or e is None:
            _add(report, sec, "warn", "设备 #%s %s 缺 U 位(s=%s,e=%s)" % (d["id"], d["name"], s, e))
            continue
        if e < s:
            _add(report, sec, "error", "设备 #%s %s U 段反转 (start=%s,end=%s)" % (d["id"], d["name"], s, e))
            continue
        if d["total_units"] and e > d["total_units"]:
            _add(report, sec, "error", "设备 #%s %s U 超限 (end=%s>机柜总高度 %s)" % (d["id"], d["name"], e, d["total_units"]))
        by_rack[d["rack_id"]].append((s, e, d["id"], d["name"]))
    for rid, segs in by_rack.items():
        segs.sort()
        for i in range(1, len(segs)):
            if segs[i][0] <= segs[i - 1][1]:
                _add(report, sec, "error", "机柜 #%s 设备 #%s 与 #%s U 位叠加" % (rid, segs[i - 1][2], segs[i][2]))
    if not any(it["level"] == "error" for it in report["sections"].get(sec, [])):
        report["summary"]["ok"] += 1


async def _audit_rack_units(conn, report):
    sec = "rack_units"
    racks = await _rows(conn, "SELECT id, code, total_units, available_units FROM racks")
    devs = await _rows(
        conn,
        "SELECT rack_id, start_u, end_u FROM devices "
        "WHERE rack_id IS NOT NULL AND start_u IS NOT NULL AND end_u IS NOT NULL",
    )
    used = defaultdict(int)
    for d in devs:
        used[d["rack_id"]] += (d["end_u"] - d["start_u"] + 1)
    for r in racks:
        total = r["total_units"] or 0
        avail = r["available_units"]
        calc = max(0, total - used.get(r["id"], 0))
        if avail is not None and calc != avail:
            _add(report, sec, "warn", "机柜 %s available_units=%s 应为 %s" % (r["code"], avail, calc))
    if not report["sections"].get(sec, []):
        report["summary"]["ok"] += 1


async def _audit_rack_layout(conn, report):
    sec = "rack_layout"
    try:
        await _rows(conn, "SELECT pos_x_m, pos_z_m, row_pos, col_pos FROM racks LIMIT 0")
        has_cols = True
    except Exception:
        has_cols = False
    if not has_cols:
        report["sections"][sec] = report["sections"].get(sec, [])
        report["summary"]["ok"] += 1
        return
    rooms = await _rows(conn, "SELECT id FROM rooms")
    miss_world = miss_rowcol = 0
    overlap = []
    for room in rooms:
        racks = await _rows(
            conn,
            "SELECT id, code, pos_x_m, pos_z_m, row_pos, col_pos FROM racks WHERE room_id=:rid",
            rid=room["id"],
        )
        keys = set()
        for r in racks:
            if r["pos_x_m"] is None or r["pos_z_m"] is None:
                miss_world += 1
            if r["row_pos"] is not None and r["col_pos"] is not None:
                k = (r["col_pos"], r["row_pos"])
                if k in keys:
                    overlap.append((r["code"], k))
                keys.add(k)
    if miss_world:
        _add(report, sec, "warn", "机柜缺世界坐标 pos_x_m/pos_z_m: %s 台" % miss_world)
    if miss_rowcol:
        _add(report, sec, "warn", "机柜缺 row/col: %s 台" % miss_rowcol)
    for code, k in overlap:
        _add(report, sec, "error", "同机房机柜坐标重叠 %s: %s" % (code, k))
    if not (miss_world or miss_rowcol or overlap):
        report["sections"][sec] = report["sections"].get(sec, [])
        report["summary"]["ok"] += 1


async def _audit_ip_ledger(conn, report):
    sec = "ip_ledger"
    dups = await _rows(conn, "SELECT address, COUNT(*) AS c FROM ip_addresses GROUP BY address HAVING c>1")
    for dd in dups:
        _add(report, sec, "error", "IP %s 重复登记 %s 条" % (dd["address"], dd["c"]))
    orphan_ip = await _rows(
        conn,
        "SELECT ip.id, ip.address, ip.device_id FROM ip_addresses ip "
        "LEFT JOIN devices d ON ip.device_id=d.id WHERE ip.device_id IS NOT NULL AND d.id IS NULL",
    )
    for x in orphan_ip:
        _add(report, sec, "error", "IP 台账 #%s %s 指向不存在的设备 #%s" % (x["id"], x["address"], x["device_id"]))
    no_rack_alloc = await _rows(
        conn,
        "SELECT ip.id, ip.address, d.id AS did, d.name, d.status "
        "FROM ip_addresses ip JOIN devices d ON ip.device_id=d.id "
        "WHERE d.rack_id IS NULL AND d.status != 'in_stock'",
    )
    for x in no_rack_alloc:
        _add(report, sec, "warn", "IP %s 由未上架设备 #%s %s(%s) 占用" % (x["address"], x["did"], x["name"], x["status"]))
    if not report["sections"].get(sec, []):
        report["summary"]["ok"] += 1


async def _audit_referential(conn, report):
    sec = "referential"
    bad_type = await _scalar(
        conn,
        "SELECT COUNT(*) FROM devices d LEFT JOIN device_types t ON d.device_type_id=t.id WHERE t.id IS NULL",
    )
    if bad_type:
        _add(report, sec, "error", "%s 台设备 device_type_id 引用不存在的设备类型" % bad_type)
    bad_subnet = await _scalar(
        conn,
        "SELECT COUNT(*) FROM ip_addresses ip LEFT JOIN ip_subnets s ON ip.subnet_id=s.id "
        "WHERE ip.subnet_id IS NOT NULL AND s.id IS NULL",
    )
    if bad_subnet:
        _add(report, sec, "error", "%s 条 IP subnet_id 引用不存在的网段" % bad_subnet)
    bad_rack_room = await _scalar(
        conn,
        "SELECT COUNT(*) FROM racks r LEFT JOIN rooms rm ON r.room_id=rm.id WHERE rm.id IS NULL",
    )
    if bad_rack_room:
        _add(report, sec, "error", "%s 个机柜 room_id 引用不存在的机房" % bad_rack_room)
    if not report["sections"].get(sec, []):
        report["summary"]["ok"] += 1


def apply_fixes(db: str | None = None) -> int:
    url = resolve_db_url(db)
    return _run(_apply_fixes_core(url))


async def _apply_fixes_core(url):
    engine = create_async_engine(url)
    fixed = 0
    try:
        async with engine.begin() as conn:
            res = await conn.execute(
                text(
                    "UPDATE ip_addresses SET device_id=NULL WHERE device_id IS NOT NULL "
                    "AND NOT EXISTS (SELECT 1 FROM devices d WHERE d.id=ip_addresses.device_id)"
                )
            )
            fixed += res.rowcount or 0
            devs = await _rows(
                conn,
                "SELECT rack_id, start_u, end_u FROM devices "
                "WHERE rack_id IS NOT NULL AND start_u IS NOT NULL AND end_u IS NOT NULL",
            )
            used = defaultdict(int)
            for d in devs:
                used[d["rack_id"]] += (d["end_u"] - d["start_u"] + 1)
            racks = await _rows(conn, "SELECT id, total_units, available_units FROM racks")
            for r in racks:
                calc = max(0, (r["total_units"] or 0) - used.get(r["id"], 0))
                if r["available_units"] != calc:
                    res = await conn.execute(
                        text("UPDATE racks SET available_units=:calc WHERE id=:rid"),
                        {"calc": calc, "rid": r["id"]},
                    )
                    fixed += res.rowcount or 0
    finally:
        await engine.dispose()
    return fixed


def format_report(report: dict) -> str:
    lines = ["=== 数据一致性检查 ===", "DB: %s" % report["db"], ""]
    for sec, items in report["sections"].items():
        if not items:
            continue
        lines.append("[%s]" % sec)
        for it in items:
            lines.append("  %-5s %s" % (it["level"].upper(), it["msg"]))
        lines.append("")
    if "info_counts" in report:
        lines.append("[info] 未上架库存设备: %s" % report["info_counts"].get("unmounted_devices", 0))
    s = report["summary"]
    lines.append("总结: ok=%s warn=%s error=%s total_findings=%s" % (
        s["ok"], s["warn"], s["error"], s["total_findings"]))
    return "\n".join(lines)
