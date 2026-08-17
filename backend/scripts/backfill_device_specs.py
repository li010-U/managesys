#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill structured device resource fields from free-text columns.

Adds cpu_cores / memory_gb / disk_capacity_gb / gpu_count / gpu_mem_gb / compute_tflops
to the devices table (idempotent ALTER), then back-fills values parsed from the existing
cpu_info / memory_info / disk_info text columns. cpu_cores uses a built-in CPU-model lookup.

Run once with the app STOPPED (or simply with the backend off). Back up the DB first.
Usage:  python scripts/backfill_device_specs.py [--db PATH] [--dry-run]
"""
import argparse
import os
import re
import sys
import sqlite3


CPU_CORES = {
    "amd epyc 7543": 32,
    "intel xeon gold 6248": 20,
    "intel xeon silver 4314": 16,
    "intel xeon silver 4214r": 12,
}

NEW_COLS = [
    ("cpu_cores", "INTEGER"),
    ("memory_gb", "FLOAT"),
    ("disk_capacity_gb", "FLOAT"),
    ("gpu_count", "INTEGER"),
    ("gpu_mem_gb", "FLOAT"),
    ("compute_tflops", "FLOAT"),
]


def _columns(conn, table):
    return [r[1] for r in conn.execute("PRAGMA table_info(" + table + ")").fetchall()]


def parse_capacity(text):
    """Parse a string like '256GB' / '4TB' / '960GB SSD' / '4TB NVMe' to GB (float) or None."""
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*(GB|TB|gB|tb|G|T)\b", text, re.IGNORECASE)
    if not m:
        return None
    try:
        value = float(m.group(1))
        unit = m.group(2).upper()
    except (ValueError, TypeError):
        return None
    if unit == "TB":
        return value * 1024.0
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "managesys.db"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    db_path = os.path.abspath(args.db)
    if not os.path.exists(db_path):
        print("DB not found:", db_path)
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    try:
        cols = _columns(conn, "devices")
        for name, ddl in NEW_COLS:
            if name not in cols:
                if not args.dry_run:
                    conn.execute("ALTER TABLE devices ADD COLUMN %s %s" % (name, ddl))
                print("  [%s] add col %s %s" % ("dry" if args.dry_run else "add", name, ddl))
            else:
                print("  exists col", name)
        if not args.dry_run:
            conn.commit()

        rows = conn.execute("SELECT id, cpu_info, memory_info, disk_info FROM devices").fetchall()
        updated = 0
        for rowid, cpu, mem, disk in rows:
            cores = None
            if cpu:
                key = cpu.strip().lower()
                cores = CPU_CORES.get(key)
            mem_gb = parse_capacity(mem)
            disk_gb = parse_capacity(disk)
            if cores is None and mem_gb is None and disk_gb is None:
                continue
            updated += 1
            if not args.dry_run:
                conn.execute('UPDATE devices SET cpu_cores=?, memory_gb=?, disk_capacity_gb=? WHERE id=?', (cores, mem_gb, disk_gb, rowid))
        if not args.dry_run:
            conn.commit()
        print("Rows backed up (cpu/mem/disk):", updated)
        unknown_cpu = set()
        for rowid, cpu, mem, disk in rows:
            if cpu and cpu.strip().lower() not in CPU_CORES:
                unknown_cpu.add(cpu.strip())
        if unknown_cpu:
            print("Unmapped CPU models (cpu_cores left NULL):", sorted(unknown_cpu))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
