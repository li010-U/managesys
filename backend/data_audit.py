# -*- coding: utf-8 -*-
"""数据一致性体检工具：检查并报告臭儿设备 / U 位叠加 /
超限 / IP 重复登记 / 未挂机柜设备等。

用法:
    python manage.py check-data                 # 仅报告
    python manage.py check-data --fix           # 报告 + 安全自动修复
    python manage.py check-data --db <path>     # 指定库
"""
from __future__ import annotations
import os
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent  # backend/

DEFAULT_DB = str(ROOT / "data" / "managesys.db")


def _conn(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or DEFAULT_DB)
    conn.row_factory = sqlite3.Row
    return conn


def run_audit(db_path: str | None = None) -> dict:
    """运行全部检查，返回结构化报告。"""
    conn = _conn(db_path)
    report = {"db": db_path or DEFAULT_DB, "sections": {}, "summary": {"ok": 0, "warn": 0, "error": 0}}
    try:
        _audit_orphan_devices(conn, report)
        _audit_u_positions(conn, report)
        _audit_rack_units(conn, report)
        _audit_ip_ledger(conn, report)
        _audit_referential(conn, report)
    finally:
        conn.close()
    # 统计合计
    total = sum(report["summary"].values())
    report["summary"]["total_findings"] = total
    return report


def _add(report: dict, section: str, level: str, msg: str):
    report["sections"].setdefault(section, []).append({"level": level, "msg": msg, "count": 0})
    report["sections"][section][-1]["count"] = 1
    report["summary"][level if level in report["summary"] else "warn"] += 1


# --- 1) 孤儿设备 ---
def _audit_orphan_devices(conn, report):
    sec = "orphan_devices"
    on_rack = conn.execute(
        "SELECT d.id, d.name, d.status, COALESCE(r.id,-1) AS rid "
        "FROM devices d LEFT JOIN racks r ON d.rack_id=r.id"
    ).fetchall()
    orphan = [r for r in on_rack if r["rid"] == -1]
    for r in orphan:
        _add(report, sec, "error",
             f"设备 #{r['id']} {r['name']} (status={r['status']}) 挂了不存在的机柜 rack_id")
    if not orphan:
        report["sections"][sec] = report["sections"].get(sec, [])
        report["summary"]["ok"] += 1


# --- 2) U 位 ---
def _audit_u_positions(conn, report):
    sec = "u_positions"
    devs = conn.execute(
        "SELECT d.id, d.name, d.rack_id, d.start_u, d.end_u, r.total_units "
        "FROM devices d JOIN racks r ON d.rack_id=r.id WHERE d.rack_id IS NOT NULL"
    ).fetchall()
    by_rack = defaultdict(list)
    for d in devs:
        s, e = d["start_u"], d["end_u"]
        if s is None or e is None:
            _add(report, sec, "warn", f"设备 #{d['id']} {d['name']} 缺 U 位(s={s},e={e})")
            continue
        if e < s:
            _add(report, sec, "error", f"设备 #{d['id']} {d['name']} U 段反转 (start={s},end={e})")
            continue
        if d["total_units"] and e > d["total_units"]:
            _add(report, sec, "error",
                 f"设备 #{d['id']} {d['name']} U 超限 (end={e}>机柜总高度{d['total_units']})")
        by_rack[d["rack_id"]].append((s, e, d["id"], d["name"]))
    for rid, segs in by_rack.items():
        segs.sort()
        for i in range(1, len(segs)):
            if segs[i][0] <= segs[i - 1][1]:
                _add(report, sec, "error",
                     f"机柜 #{rid} 设备 #{segs[i-1][2]} 与 #{segs[i][2]} U 位叠加")
    if not any(r["level"] == "error" for r in report["sections"].get(sec, [])):
        report["summary"]["ok"] += 1


# --- 3) 机柜 U 位总计一致性 ---
def _audit_rack_units(conn, report):
    sec = "rack_units"
    racks = conn.execute("SELECT id, code, total_units, available_units FROM racks").fetchall()
    devs = conn.execute(
        "SELECT rack_id, start_u, end_u FROM devices WHERE rack_id IS NOT NULL AND start_u IS NOT NULL AND end_u IS NOT NULL"
    ).fetchall()
    used = defaultdict(int)
    for d in devs:
        used[d["rack_id"]] += (d["end_u"] - d["start_u"] + 1)
    for r in racks:
        total = r["total_units"] or 0
        avail = r["available_units"] or 0
        calc_free = max(0, total - used.get(r["id"], 0))
        if total and abs(calc_free - avail) > 0:
            _add(report, sec, "warn",
                 f"机柜 {r['code']} #{r['id']} available_units={avail} 与根据设备推算的离置位={calc_free} 不同")
    if not report["sections"].get(sec, []):
        report["summary"]["ok"] += 1


# --- 4) IP 台账 ---
def _audit_ip_ledger(conn, report):
    sec = "ip_ledger"
    # 4.1 重复地址
    dups = conn.execute(
        "SELECT address, count(*) c FROM ip_addresses GROUP BY address HAVING c>1"
    ).fetchall()
    for d in dups:
        _add(report, sec, "error", f"IP {d['address']} 重复登记 {d['c']} 条")
    # 4.2 参考了不存在的设备
    orphan_ip = conn.execute(
        "SELECT ip.id, ip.address, ip.device_id FROM ip_addresses ip "
        "LEFT JOIN devices d ON ip.device_id=d.id WHERE ip.device_id IS NOT NULL AND d.id IS NULL"
    ).fetchall()
    for ip in orphan_ip:
        _add(report, sec, "error",
             f"IP 台账 #{ip['id']} {ip['address']} 指向不存在的设备 #{ip['device_id']}")
    # 4.3 未挂机柜设备（status 非 in_stock 但无 rack）却占用 IP
    no_rack_alloc = conn.execute(
        "SELECT ip.id, ip.address, d.id did, d.name, d.status "
        "FROM ip_addresses ip JOIN devices d ON ip.device_id=d.id "
        "WHERE d.rack_id IS NULL AND d.status != 'in_stock'"
    ).fetchall()
    for ip in no_rack_alloc:
        _add(report, sec, "warn",
             f"IP {ip['address']} 被未挂机柜的设备 #{ip['did']} {ip['name']}({ip['status']}) 占用")
    if not report["sections"].get(sec, []):
        report["summary"]["ok"] += 1


# --- 5) 引用完整性 ---
def _audit_referential(conn, report):
    sec = "referential"
    bad_type = conn.execute(
        "SELECT count(*) c FROM devices d LEFT JOIN device_types t ON d.device_type_id=t.id WHERE t.id IS NULL"
    ).fetchone()["c"]
    if bad_type:
        _add(report, sec, "error", f"{bad_type} 台设备 device_type_id 引用不存在的设备类型")
    bad_subnet = conn.execute(
        "SELECT count(*) c FROM ip_addresses ip LEFT JOIN ip_subnets s ON ip.subnet_id=s.id WHERE ip.subnet_id IS NOT NULL AND s.id IS NULL"
    ).fetchone()["c"]
    if bad_subnet:
        _add(report, sec, "error", f"{bad_subnet} 条 IP subnet_id 引用不存在的网段")
    bad_rack_room = conn.execute(
        "SELECT count(*) c FROM racks r LEFT JOIN rooms rm ON r.room_id=rm.id WHERE rm.id IS NULL"
    ).fetchone()["c"]
    if bad_rack_room:
        _add(report, sec, "error", f"{bad_rack_room} 个机柜 room_id 引用不存在的机房")
    if not report["sections"].get(sec, []):
        report["summary"]["ok"] += 1


# --- 报告输出 ---

# --- 安全自动修复（仅淡化已知安全的引用缺陷）---
def apply_fixes(db_path):
    """执行保守修复：爯发达到的只是IP指向不存在设备这类明确安全的引用缺陷。
    其余问题（孤儿设备、U位叠加等）需人工确认，不自动移除。"""
    conn = sqlite3.connect(db_path or DEFAULT_DB)
    fixed = 0
    try:
        cur = conn.execute(
            "UPDATE ip_addresses SET device_id=NULL WHERE device_id IS NOT NULL "
            "AND NOT EXISTS (SELECT 1 FROM devices d WHERE d.id=ip_addresses.device_id)"
        )
        fixed += cur.rowcount
        conn.commit()
    finally:
        conn.close()
    return fixed

def format_report(report: dict) -> str:
    lines = ["=== 数据一致性体检 ===", f"DB: {report['db']}", ""]
    for sec, items in report["sections"].items():
        if not items:
            continue
        lines.append(f"[{sec}]")
        for it in items:
            level = it["level"]
            lines.append(f"  {level.upper():5} {it['msg']}")
        lines.append("")
    s = report["summary"]
    lines.append(f"总结: ok={s['ok']} warn={s['warn']} error={s['error']} total_findings={s['total_findings']}")
    return "\n".join(lines)
