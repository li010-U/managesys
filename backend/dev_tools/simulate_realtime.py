import _guard
import argparse
import sqlite3
import os
import sys
import random
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from app.core.timeutil import now_local

DB_PATH = str(Path(__file__).resolve().parents[1] / 'data' / 'managesys.db')


def update_sensors(interval_us: int, per_cycle: int, alert_prob: float):
    """每秒一轮：从传感器中采样 per_cycle 个，各自以真实时间戳（微秒抖动）写一条新采样。

    interval_us: 本轮循环期望间隔（微秒），用于让同一批内的时间戳尽量错开，贴近真实采样。
    """
    conn = sqlite3.connect(DB_PATH, timeout=30)  # busy_timeout 30s，撞锁耐心等待，避免与 web 服务互抢
    c = conn.cursor()
    c.execute('SELECT id, code, sensor_type, threshold_min, threshold_max, alert_level FROM sensors')
    all_sensors = c.fetchall()

    # 默认每秒更新全部传感器；per_cycle 限制可收缩
    if per_cycle and per_cycle < len(all_sensors):
        selected = random.sample(all_sensors, per_cycle)
    else:
        selected = all_sensors

    base = now_local()
    alerts_created = 0
    step = max(interval_us // max(len(selected), 1), 1)

    for idx, (sensor_id, code, sensor_type, min_val, max_val, alert_level) in enumerate(selected):
        # 用微秒把同一批内的记录时间错开，避免"同秒完全对齐"的造假形状
        point_ts = base + timedelta(microseconds=step * idx)
        now = point_ts.strftime('%Y-%m-%d %H:%M:%S.%f')

        if sensor_type in ('smoke', 'door_magnetic'):
            value = random.choice([0, 0, 0, 1])
            json_value = '{"value": %s, "unit": ""}' % value
            threshold = max_val * 0.8 if max_val else 0.5
            is_alert = value >= threshold and threshold > 0
        else:
            center = (min_val + max_val) / 2 if max_val and min_val else 50
            value = random.gauss(center, (max_val - min_val) / 4 if max_val and min_val else 20)
            value = max(min_val or 0, min(max_val or 100, value))
            unit = 'C' if sensor_type == 'temperature' else '%' if sensor_type == 'humidity' else 'kW'
            json_value = '{"value": %s, "unit": "%s"}' % (round(value, 2), unit)
            threshold = max_val * 0.85 if max_val else 100
            is_alert = value > threshold

        c.execute(
            "UPDATE sensors SET current_value=?, last_update_time=?, status='online' WHERE id=?",
            (json_value, now, sensor_id)
        )
        # 异常(越限/告警)采样点标记 abnormal，交由后端 180 天保留；
        # 正常模拟点标记 sim，由本模拟器按 keep_hours 滚动清理。
        source_mark = 'abnormal' if is_alert else 'sim'
        c.execute(
            "INSERT INTO sensor_data (sensor_id, value, recorded_at, source_mark) VALUES (?, ?, ?, ?)",
            (sensor_id, round(value, 2), now, source_mark)
        )

        if is_alert and random.random() < alert_prob:
            title = '%s 监测值异常' % sensor_type
            desc = '当前值: %.2f, 阈值: %.2f' % (value, threshold)
            c.execute(
                "INSERT INTO alerts (target_type, target_id, title, description, level, status, source, created_at) "
                "VALUES ('sensor', ?, ?, ?, ?, 'new', 'monitor', ?)",
                (str(sensor_id), title, desc, alert_level, now)
            )
            alerts_created += 1

    conn.commit()
    conn.close()
    return len(selected), alerts_created


def _cleanup_sensor_data(conn, keep_hours: float, keep_rows: int = 0):
    """按时间清理正常模拟数据(sim)与可选的异常数据兜底。

    - 只删除本模拟器写的、超过 keep_hours 的正常(sim)数据；
    - 异常(abnormal)数据默认不移除，交由后端 DATA_RETENTION_DAYS(180天) 保留；
    - keep_rows>0 时可作为异常数据最大行数的可选兜底（默认 0=不设上限）。
    """
    c = conn.cursor()
    cutoff = (datetime.now() - timedelta(hours=keep_hours)).strftime('%Y-%m-%d %H:%M:%S.%f')
    c.execute(
        "DELETE FROM sensor_data WHERE source_mark = 'sim' AND recorded_at < ?",
        (cutoff,)
    )
    if keep_rows and keep_rows > 0:
        c.execute(
            "DELETE FROM sensor_data WHERE source_mark = 'abnormal' AND id NOT IN "
            "(SELECT id FROM sensor_data WHERE source_mark = 'abnormal' ORDER BY id DESC LIMIT ?)",
            (keep_rows,)
        )
    conn.commit()
    return c.rowcount


def _main():
    parser = argparse.ArgumentParser(description='Real-time sensor simulation (每秒采样, 贴近真实生产).')
    parser.add_argument('--interval', type=float, default=1.0, help='每轮间隔秒数 (默认 1.0 秒)')
    parser.add_argument('--per-cycle', type=int, default=0, help='每轮更新传感器数量 (0=全部)')
    parser.add_argument('--alert-prob', type=float, default=0.05, help='越限时生成告警概率 (默认 0.05)')
    parser.add_argument('--keep-hours', type=float, default=24.0, help='正常模拟数据保留小时数 (默认 24 小时)')
    parser.add_argument('--keep-rows', type=int, default=0, help='异常数据保留的最大行数上限，0=不设上限(由后端180天保留管理)')
    args = parser.parse_args()

    _guard.ensure_dev_mode()

    interval_us = max(int(args.interval * 1_000_000), 100_000)
    print('Starting real-time sensor simulation (每秒采样)...')
    print('Press Ctrl+C to stop')
    print()

    iteration = 0
    try:
        while True:
            iteration += 1
            tick = datetime.now()
            updated, alerts_created = update_sensors(interval_us, args.per_cycle, args.alert_prob)
            now_s = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            line = f'[{now_s}] Updated {updated} sensors'
            if alerts_created:
                line += f' | Created {alerts_created} alerts'
            print(line, flush=True)

            if iteration % 60 == 0:  # 每分钟清理一次，保持数据窗口可控
                conn = sqlite3.connect(DB_PATH, timeout=30)  # busy_timeout 30s，撞锁耐心等待，避免与 web 服务互抢
                _cleanup_sensor_data(conn, args.keep_hours, args.keep_rows)
                conn.close()
                print(f'[{datetime.now().strftime("%H:%M:%S")}] cleaned normal sensor_data (keep {args.keep_hours}h)', flush=True)

            # 剩余时间补偿：让每轮尽可能贴近 interval
            elapsed_us = int((datetime.now() - tick).total_seconds() * 1_000_000)
            sleep_us = interval_us - elapsed_us
            if sleep_us > 0:
                import time
                time.sleep(sleep_us / 1_000_000)
    except KeyboardInterrupt:
        print('\nSimulation stopped.')


if __name__ == '__main__':
    _main()