# -*- coding: utf-8 -*-
"""数据一致性体检工具测试。
对应优化方案第④项“数据一致性体检工具/脚本”。
"""
import os
import sqlite3
import tempfile

import data_audit


def _make_db() -> str:
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    c = sqlite3.connect(p)
    c.executescript("""
    CREATE TABLE device_types (id INTEGER PRIMARY KEY);
    CREATE TABLE rooms (id INTEGER PRIMARY KEY);
    CREATE TABLE ip_subnets (id INTEGER PRIMARY KEY);
    CREATE TABLE racks (
        id INTEGER PRIMARY KEY, code TEXT, room_id INTEGER, total_units INTEGER, available_units INTEGER
    );
    CREATE TABLE devices (
        id INTEGER PRIMARY KEY, name TEXT, status TEXT, rack_id INTEGER, device_type_id INTEGER,
        start_u INTEGER, end_u INTEGER
    );
    CREATE TABLE ip_addresses (
        id INTEGER PRIMARY KEY, address TEXT, device_id INTEGER, status TEXT, subnet_id INTEGER
    );
    -- room / subnet / device_type for valid refs
    INSERT INTO rooms VALUES (1);
    INSERT INTO ip_subnets VALUES (1);
    INSERT INTO device_types VALUES (1);
    -- rack A: total 42, two devices U1-4 and U3-6 (overlap), avail should be 38
    INSERT INTO racks VALUES (1, 'A-01', 1, 42, 42);
    -- device on rack A
    INSERT INTO devices VALUES (1,'srv1','online',1,1,1,4);
    -- U overlap: U3-6 overlaps U1-4
    INSERT INTO devices VALUES (2,'srv2','online',1,1,3,6);
    -- orphan device: rack_id=999 (nonexistent)
    INSERT INTO devices VALUES (3,'orphan','in_stock',999,1,NULL,NULL);
    -- device_type ref bad
    INSERT INTO devices VALUES (4,'badtype','online',1,888,1,1);
    -- IP orphan ref to nonexistent device 999
    INSERT INTO ip_addresses VALUES (1,'10.0.0.1',999,'allocated',1);
    -- duplicate address
    INSERT INTO ip_addresses VALUES (2,'10.0.0.2',1,'allocated',1);
    INSERT INTO ip_addresses VALUES (3,'10.0.0.2',1,'allocated',1);
    """)
    c.commit()
    c.close()
    return p


def test_audit_finds_inconsistencies():
    p = _make_db()
    try:
        r = data_audit.run_audit(p)
        secs = r["sections"]
        # orphan device (rack_id 999)
        assert any("\u6302\u4e86\u4e0d\u5b58\u5728\u7684\u673a\u67dc" in it["msg"] for it in secs.get("orphan_devices", []))
        # U overlap on rack A
        assert any("U \u4f4d\u53e0\u52a0" in it["msg"] for it in secs.get("u_positions", []))
        # rack available_units mismatch
        assert any("available_units" in it["msg"] for it in secs.get("rack_units", []))
        # duplicate ip
        assert any("\u91cd\u590d\u767b\u8bb0" in it["msg"] for it in secs.get("ip_ledger", []))
        # orphan ip ref
        assert any("\u4e0d\u5b58\u5728\u7684\u8bbe\u5907" in it["msg"] for it in secs.get("ip_ledger", []))
        # bad device_type ref
        assert any("device_type_id" in it["msg"] for it in secs.get("referential", []))
        assert r["summary"]["error"] >= 1
    finally:
        os.remove(p)


def test_apply_fixes_clears_orphan_ip_ref_only():
    p = _make_db()
    try:
        data_audit.apply_fixes(p)
        c = sqlite3.connect(p)
        orphan = c.execute("SELECT count(*) FROM ip_addresses WHERE device_id IS NOT NULL "
                           "AND NOT EXISTS (SELECT 1 FROM devices d WHERE d.id=ip_addresses.device_id)").fetchone()[0]
        assert orphan == 0
        # valid refs preserved
        valid = c.execute("SELECT count(*) FROM ip_addresses WHERE device_id IN (1)").fetchone()[0]
        assert valid == 2
        c.close()
    finally:
        os.remove(p)
