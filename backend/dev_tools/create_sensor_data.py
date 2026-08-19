# -*- coding: utf-8 -*-
"""生成传感器历史采样数据（仅限开发环境，写入会被 _guard 拦截）。

用途: 为演示/联调生成一条"看起来像历史采样"的时间序列。

安全护栏（相对旧版的关键改进）:
  1. 默认只打印不写库（--dry-run 可显式开启，缺省即 dry-run）。
  2. 必须 ALLOW_DEV_TOOL_WRITE=1 才允许实际写库（旧逻辑会隐性覆盖真实数据）。
  3. 时间戳加入随机抖动, 避免"68 个传感器整点半秒 68 条同秒对齐"的假序列。
  4. 不再用显式 id 从 1 递增覆盖既有记录（改用自增 id, 避免 id 乱序/覆盖）。
  5. 写入带 source_mark='backfill', 便于从真实采样中区分。
所有时间统一走 app.core.timeutil.now_local()（本地 naive 口径）。
"""
import _guard
import argparse
import os
import random
import sqlite3
from datetime import timedelta
from pathlib import Path

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from app.core.timeutil import now_local

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "managesys.db"
db_path = str(DB_PATH)

def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="只打印将要插入的内容，不写入数据库（默认 dry-run，除非传 --really-write）")
    parser.add_argument("--really-write", action="store_true",
                        help="真正写入数据库（仍需 ALLOW_DEV_TOOL_WRITE=1）")
    parser.add_argument("--samples", type=int, default=48,
                        help="每个传感器生成多少条采样（默认 48）")
    parser.add_argument("--interval-min", type=int, default=30,
                        help="采样间隔分钟数（默认 30）")
    parser.add_argument("--seed", type=int, default=None, help="随机种子，便于复现")
    parser.add_argument("--no-jitter", action="store_true",
                        help="关闭时间抖动（默认开启，开启更贴近真实采样步长）")
    args = parser.parse_args()

    if not (args.dry_run or args.really_write):
        print("[!] 请明确指定 --dry-run（仅预览）或 --really-write（实际写库）。")
        sys_exit(2)

    if not args.dry_run:
        _guard.ensure_dev_mode()

    if args.seed is not None:
        random.seed(args.seed)

    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("SELECT id, threshold_min, threshold_max, sensor_type FROM sensors")
    sensors = c.fetchall()
    print(f"Sensors: {len(sensors)}")

    # 仅当 --really-write 才提交。
    action = "DRY-RUN(不写库)" if args.dry_run else "WRITE(写库)"
    base_time = now_local()
    data_count = 0
    for sensor_id, min_val, max_val, sensor_type in sensors:
        for i in range(args.samples):
            if sensor_type in ("smoke", "door_magnetic"):
                value = random.choice([0, 0, 0, 0, 1])
            else:
                value = random.uniform(min_val or 0, max_val or 100)
            if args.no_jitter:
                recorded_at = base_time - timedelta(minutes=args.interval_min * (args.samples - 1 - i))
            else:
                # 抖动: 每条采样时间在连续区间内随机，避免同一秒对齐
                recorded_at = base_time - timedelta(
                    minutes=args.interval_min * (args.samples - 1 - i),
                    seconds=random.randint(0, args.interval_min * 60 - 1),
                )
            ts = recorded_at.strftime("%Y-%m-%d %H:%M:%S.%f")
            if args.dry_run:
                print(f"  [{action}] sensor={sensor_id} value={value:.2f} recorded_at={ts}")
            else:
                c.execute(
                    "INSERT INTO sensor_data (sensor_id, value, recorded_at, source_mark) VALUES (?, ?, ?, 'backfill')",
                    (sensor_id, round(value, 2), ts),
                )
            data_count += 1

    if args.really_write:
        conn.commit()
        c.execute("SELECT COUNT(*) FROM sensor_data")
        print(f"Data records created: {data_count} ; total sensor data: {c.fetchone()[0]}")
    else:
        print(f"[DRY-RUN] 共预览 {data_count} 条，未写入任何数据。")
    conn.close()

def sys_exit(code):
    import sys
    sys.exit(code)

if __name__ == "__main__":
    _main()
