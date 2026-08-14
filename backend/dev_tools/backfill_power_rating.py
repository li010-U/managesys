# -*- coding: utf-8 -*-
import _guard
_guard.ensure_dev_mode()
"""回填存量设备功率 (power_rating) 的一次性脚本。

背景：power_rating 字段是后续 ALTER TABLE 加的，存量 705 台设备全部为 NULL，
导致 AI 智能分析-容量规划里"功率kW"和"供电负载"恒为 0。

本脚本按设备类型(device_type.name / category)或设备名前缀给出合理默认功率，
只回填当前为 NULL/0 的设备，幂等可重复执行。

用法：
    python backfill_power_rating.py            # 预览（dry-run，不写库）
    python backfill_power_rating.py --apply    # 真正写库
    python backfill_power_rating.py --force    # 连同已有值一起覆盖（谨慎）
"""
import argparse
import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "managesys.db")

# 按设备类型名称 -> 默认功率(kW)。可自行调整。
TYPE_DEFAULTS = {
    "服务器": 0.8,        # 标准 1U/2U 服务器
    "网络设备": 0.5,      # 交换机/路由器
    "存储设备": 1.2,      # SAN/存储阵列
    "安全设备": 0.4,      # 防火墙/安全设备
    "UPS": 2.0,           # 不间断电源
    "精密空调": 4.0,      # 机房精密空调
}

# 按设备名前缀 -> 默认功率(kW)，作为类型查询失败的兜底。
NAME_PREFIX_DEFAULTS = {
    "SERVER": 0.8,
    "NETWORK": 0.5,
    "STORAGE": 1.2,
    "SECURITY": 0.4,
    "UPS": 2.0,
    "AC": 4.0,
}


def load_type_power_map(cur):
    """返回 {device_type_name: power_kw}，用于按类型匹配。"""
    cur.execute("SELECT id, name, category FROM device_types")
    rows = cur.fetchall()
    m = {}
    for tid, name, category in rows:
        name = (name or "").strip()
        category = (category or "").strip()
        if name in TYPE_DEFAULTS:
            m[tid] = TYPE_DEFAULTS[name]
        elif category in TYPE_DEFAULTS:
            m[tid] = TYPE_DEFAULTS[category]
    return m


def infer_power(dtype_name, dev_name):
    """按设备类型名/前缀推断默认功率，找不到返回 None。"""
    if dtype_name in TYPE_DEFAULTS:
        return TYPE_DEFAULTS[dtype_name]
    dev_up = (dev_name or "").upper()
    for prefix, kw in NAME_PREFIX_DEFAULTS.items():
        if dev_up.startswith(prefix):
            return kw
    return None


def main():
    ap = argparse.ArgumentParser(description="回填存量设备功率 power_rating")
    ap.add_argument("--apply", action="store_true", help="真正写库（默认仅预览 dry-run）")
    ap.add_argument("--force", action="store_true", help="连同已有非零值一起覆盖")
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    type_map = load_type_power_map(cur)

    # 取出需要处理的设备
    if args.force:
        cur.execute("""SELECT d.id, d.name, d.power_rating, dt.name, d.device_type_id
                       FROM devices d LEFT JOIN device_types dt ON d.device_type_id=dt.id""")
    else:
        cur.execute("""SELECT d.id, d.name, d.power_rating, dt.name, d.device_type_id
                       FROM devices d LEFT JOIN device_types dt ON d.device_type_id=dt.id
                       WHERE d.power_rating IS NULL OR d.power_rating = 0""")
    rows = cur.fetchall()

    by_type = {}
    unmatched = []
    to_update = []
    for did, dname, old_pw, dtype_name, tid in rows:
        kw = None
        if tid in type_map:
            kw = type_map[tid]
        else:
            kw = infer_power(dtype_name, dname)
        if kw is None:
            unmatched.append((did, dname, dtype_name))
            continue
        to_update.append((kw, did))
        by_type.setdefault(dtype_name or "(无名类型)", [0, 0])[0] += 1
        if old_pw is None or old_pw == 0:
            by_type[dtype_name or "(无名类型)"][1] += 1

    print(f"待处理设备: {len(rows)} 台")
    print(f"可回填: {len(to_update)} 台")
    print("按类型分布(= 待处理 / 其中为0):")
    for t, (n, zero_n) in sorted(by_type.items(), key=lambda x: -x[1][0]):
        print(f"  {t:<12} {n:>4} 台 (原为0/空: {zero_n})")

    if unmatched:
        print("\n无法匹配默认功率(保持原值):")
        for did, dname, dt in unmatched[:20]:
            print(f"  id={did} name={dname} type={dt}")

    if not args.apply:
        print("\n[dry-run] 未写库，加 --apply 执行回填。")
        conn.close()
        return

    cur.executemany("UPDATE devices SET power_rating=?, updated_at=datetime('now') WHERE id=?", to_update)
    conn.commit()
    total = cur.rowcount  # 注意 executemany 后 rowcount 语义，仅作说明
    print(f"\n已回填 {len(to_update)} 台设备 (total rows affected: {cur.rowcount})")
    conn.close()


if __name__ == "__main__":
    main()
