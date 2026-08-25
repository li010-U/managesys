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

# ===== 告警生命周期确定性口径（与 backend/app/services/alert_lifecycle_service.py 保持一致） =====
# - 去重：同一设备(target_type+target_id)在未解决(open)期间不再新建重复告警，仅刷新最近异常时间。
# - 自动解决：参数连续正常 >= auto_resolve_minutes 分钟后标记「已解决」。
# - 冷却防抖：已解决后再次异常，需经过 cooldown_minutes 冷却才能重新告警。
# - 短时自愈：异常在 transient_max_seconds 内恢复 => 偶发故障，登记 transient_failure_events 且不打扰。

_TS_FMT = '%Y-%m-%d %H:%M:%S'
_TS_FMT_US = '%Y-%m-%d %H:%M:%S.%f'


def _coerce_dt(v):
    """把 SQLite 读回的文本时间(DATETIME)转成 datetime；已是 datetime 则原样返回。"""
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    s = str(v)
    try:
        return datetime.strptime(s, _TS_FMT)
    except ValueError:
        pass
    try:
        return datetime.strptime(s, _TS_FMT_US)
    except ValueError:
        pass
    return None


def _fmt_dt(v):
    """把 datetime 转为与库中其它告警一致的文本时间(带微秒)；None/str 原样返回。"""
    if v is None or isinstance(v, str):
        return v
    if isinstance(v, datetime):
        return v.strftime(_TS_FMT_US)
    return v


def _ensure_transient_event(conn, c, alert_row, recovered_at, duration):
    """幂等登记偶发故障事件(同一 alert 只登记一次)。"""
    (alert_id, target_type, target_id, title, first_seen_at) = alert_row
    dup = c.execute(
        "SELECT id FROM transient_failure_events WHERE alert_id = ? LIMIT 1", (alert_id,)
    ).fetchone()
    if dup:
        return
    created_at = datetime.now()
    c.execute(
        "INSERT INTO transient_failure_events "
        "(alert_id, target_type, target_id, metric, title, started_at, recovered_at, duration_seconds, created_at) "
        "VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?)",
        (alert_id, target_type, target_id, title, _fmt_dt(first_seen_at),
         _fmt_dt(recovered_at), duration, _fmt_dt(created_at)),
    )


def register_signal(conn, target_type, target_id, is_abnormal, *,
                    title=None, level='general', device_id=None, source='monitor',
                    observed_at=None, auto_resolve_minutes=30, transient_max_seconds=300,
                    cooldown_minutes=5):
    """同步版 register_signal：去重 / 冷却 / 短时自愈 / 恢复。返回 action。"""
    observed_at = observed_at or now_local()
    c = conn.cursor()

    open_alert = c.execute(
        "SELECT id, first_seen_at, created_at, target_type, target_id, title, is_transient "
        "FROM alerts WHERE target_type=? AND target_id=? AND status IN ('new','acknowledged') "
        "ORDER BY created_at ASC LIMIT 1",
        (target_type, str(target_id)),
    ).fetchone()

    if not is_abnormal:
        # ===== 恢复正常信号 =====
        if open_alert is None:
            return {'action': 'nothing', 'transient': False}
        alert_id, first_seen, created_at, ttype, tid, atitle, is_transient = open_alert
        first_dt = _coerce_dt(first_seen) or _coerce_dt(created_at)
        elapsed = (observed_at - first_dt).total_seconds() if first_dt else 0
        c.execute(
            "UPDATE alerts SET normal_since_at=? WHERE id=?",
            (_fmt_dt(observed_at), alert_id),
        )
        if not is_transient and 0 < elapsed <= transient_max_seconds:
            # 短时自愈：登记偶发故障，不推送
            c.execute(
                "UPDATE alerts SET is_transient=1, lifecycle_action='transient', duration_seconds=? WHERE id=?",
                (int(elapsed), alert_id),
            )
            row = (alert_id, ttype, tid, atitle, first_dt)
            _ensure_transient_event(conn, c, row, observed_at, int(elapsed))
            return {'action': 'transient_created', 'alert_id': alert_id,
                    'transient': True, 'duration_seconds': int(elapsed)}
        return {'action': 'recovered', 'alert_id': alert_id, 'transient': bool(is_transient)}

    # ===== 异常信号 =====
    if open_alert is not None:
        # 去重：刷新最近异常时间与累计次数
        c.execute(
            "UPDATE alerts SET last_abnormal_at=?, status='new', occurrences=COALESCE(occurrences,1)+1 "
            "WHERE id=?",
            (_fmt_dt(observed_at), open_alert[0]),
        )
        return {'action': 'updated', 'alert_id': open_alert[0], 'status': 'new'}

    # 无开放告警：冷却防抖
    recent = c.execute(
        "SELECT id, resolved_at FROM alerts WHERE target_type=? AND target_id=? AND status='resolved' "
        "ORDER BY resolved_at DESC LIMIT 1",
        (target_type, str(target_id)),
    ).fetchone()
    if recent is not None and recent[1] is not None:
        _rr = _coerce_dt(recent[1])
        cooldown_until = (_rr + timedelta(minutes=cooldown_minutes)) if _rr else None
        if cooldown_until is not None and cooldown_until > observed_at:
            c.execute("UPDATE alerts SET cooldown_until=? WHERE id=?", (_fmt_dt(cooldown_until), recent[0]))
            return {'action': 'suppressed_cooldown', 'alert_id': recent[0], 'cooldown_until': cooldown_until}

    # 新建告警
    cur = c.execute(
        "INSERT INTO alerts "
        "(alert_rule_id, device_id, target_type, target_id, title, description, level, status, source, "
        " created_at, first_seen_at, last_abnormal_at, normal_since_at, auto_resolve_minutes, dedupe_key, occurrences) "
        "VALUES (NULL, ?, ?, ?, ?, ?, ?, 'new', ?, ?, ?, ?, NULL, ?, ?, 1)",
        (device_id, target_type, str(target_id), title or ('%s:%s 异常' % (target_type, target_id)),
         None, level, source, _fmt_dt(observed_at), _fmt_dt(observed_at), _fmt_dt(observed_at),
         auto_resolve_minutes, '%s|%s' % (target_type, str(target_id))),
    )
    alert_id = cur.lastrowid
    return {'action': 'created', 'alert_id': alert_id, 'status': 'new'}


def sweep_auto_resolve(conn, auto_resolve_minutes=30, cooldown_minutes=5):
    """自动恢复：参数连续正常 >= auto_resolve_minutes 分钟后标「已解决」。"""
    now = now_local()
    cutoff = now - timedelta(minutes=auto_resolve_minutes)
    c = conn.cursor()
    rows = c.execute(
        "SELECT id, last_abnormal_at, first_seen_at, created_at, is_transient "
        "FROM alerts WHERE status IN ('new','acknowledged') AND normal_since_at IS NOT NULL "
        "AND normal_since_at <= ?",
        (_fmt_dt(cutoff),),
    ).fetchall()
    resolved_ids = []
    for (alert_id, last_abnormal_at, first_seen_at, created_at, is_transient) in rows:
        start = _coerce_dt(last_abnormal_at) or _coerce_dt(first_seen_at) or _coerce_dt(created_at)
        duration = max(0, int((now - start).total_seconds())) if start else 0
        c.execute(
            "UPDATE alerts SET status='resolved', resolved_at=?, lifecycle_action='auto_resolve', "
            "cooldown_until=?, duration_seconds=? WHERE id=?",
            (_fmt_dt(now), _fmt_dt(now + timedelta(minutes=cooldown_minutes)), duration, alert_id),
        )
        resolved_ids.append(alert_id)
    return resolved_ids


# 每个传感器持续异常计数（内存态，配合 for-duration 持续窗口）
_STATE = {}


def _get_state(sensor_id):
    st = _STATE.get(sensor_id)
    if st is None:
        st = {'consec': 0}
        _STATE[sensor_id] = st
    return st


def update_sensors(interval_us, per_cycle, alert_prob, consecutive, auto_resolve_minutes,
                   transient_max_seconds, cooldown_minutes, lifecycle_enabled):
    """每秒一轮：采样传感器，写采样数据，并经生命周期引擎登记告警/恢复。"""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()
    c.execute('SELECT id, code, sensor_type, threshold_min, threshold_max, alert_level FROM sensors')
    all_sensors = c.fetchall()

    if per_cycle and per_cycle < len(all_sensors):
        selected = random.sample(all_sensors, per_cycle)
    else:
        selected = all_sensors

    base = now_local()
    step = max(interval_us // max(len(selected), 1), 1)

    for idx, (sensor_id, code, sensor_type, min_val, max_val, alert_level) in enumerate(selected):
        point_ts = base + timedelta(microseconds=step * idx)
        now_ts = point_ts.strftime('%Y-%m-%d %H:%M:%S.%f')

        if sensor_type in ('smoke', 'door'):
            # 开关型：door/smoke。1=触发，0=正常。
            # 修复误报：烟感极低概率真实报警；门开合算常态，均需连续 N 次置1 才判异常。
            state = _get_state(sensor_id)
            if sensor_type == 'smoke':
                raw = 1 if random.random() < 0.002 else 0
            else:  # door
                raw = 1 if random.random() < 0.30 else 0
            state['consec'] = (state['consec'] + 1) if raw == 1 else 0
            is_abnormal = state['consec'] >= consecutive
            value = raw
            json_value = '{"value": %s, "unit": ""}' % value
        else:
            # 连续型：temperature/humidity/power。收紧噪声(range/12≈3σ)，仅真实漂移触发。
            center = (min_val + max_val) / 2 if max_val and min_val else 50
            sigma = (max_val - min_val) / 12.0 if max_val and min_val else 20
            value = random.gauss(center, sigma)
            value = max(min_val or 0, min(max_val or 100, value))
            unit = 'C' if sensor_type == 'temperature' else '%' if sensor_type == 'humidity' else 'kW'
            json_value = '{"value": %s, "unit": "%s"}' % (round(value, 2), unit)
            threshold = max_val * 0.85 if max_val else 100
            state = _get_state(sensor_id)
            over = value > threshold
            state['consec'] = (state['consec'] + 1) if over else 0
            is_abnormal = state['consec'] >= consecutive
            # 偶发真实漂移：触发持续越阈，制造真实告警
            if over and state['consec'] == 1 and random.random() < alert_prob:
                state['_drift'] = consecutive

        c.execute(
            "UPDATE sensors SET current_value=?, last_update_time=?, status='online' WHERE id=?",
            (json_value, now_ts, sensor_id),
        )
        source_mark = 'abnormal' if is_abnormal else 'sim'
        c.execute(
            "INSERT INTO sensor_data (sensor_id, value, recorded_at, source_mark) VALUES (?, ?, ?, ?)",
            (sensor_id, round(value, 2), now_ts, source_mark),
        )

        # P0 核心：经生命周期登记
        if lifecycle_enabled:
            register_signal(
                conn, 'sensor', str(sensor_id), is_abnormal,
                title='%s 监测值异常' % sensor_type,
                level=alert_level,
                source='monitor',
                observed_at=now_local(),
                auto_resolve_minutes=auto_resolve_minutes,
                transient_max_seconds=transient_max_seconds,
                cooldown_minutes=cooldown_minutes,
            )

    if lifecycle_enabled:
        try:
            sweep_auto_resolve(conn, auto_resolve_minutes, cooldown_minutes)
        except Exception:
            conn.rollback()
            sweep_auto_resolve(conn, auto_resolve_minutes, cooldown_minutes)
    conn.commit()
    conn.close()
    return len(selected)


def _cleanup_sensor_data(conn, keep_hours, keep_rows=0):
    c = conn.cursor()
    cutoff = (datetime.now() - timedelta(hours=keep_hours)).strftime('%Y-%m-%d %H:%M:%S.%f')
    c.execute("DELETE FROM sensor_data WHERE source_mark = 'sim' AND recorded_at < ?", (cutoff,))
    if keep_rows and keep_rows > 0:
        c.execute(
            "DELETE FROM sensor_data WHERE source_mark = 'abnormal' AND id NOT IN "
            "(SELECT id FROM sensor_data WHERE source_mark = 'abnormal' ORDER BY id DESC LIMIT ?)",
            (keep_rows,),
        )
    conn.commit()
    return c.rowcount


def _main():
    parser = argparse.ArgumentParser(description='Real-time sensor simulation with alert lifecycle.')
    parser.add_argument('--interval', type=float, default=1.0, help='每轮间隔秒数(默认 1.0)')
    parser.add_argument('--per-cycle', type=int, default=0, help='每轮更新传感器数量(0=全部)')
    parser.add_argument('--alert-prob', type=float, default=0.05, help='连续型真实漂移触发概率(默认 0.05)')
    parser.add_argument('--consecutive', type=int, default=3, help='持续越阈多少次才判异常(默认3, for-duration)')
    parser.add_argument('--auto-resolve-minutes', type=int, default=30, help='连续正常多久自动解决(默认30)')
    parser.add_argument('--transient-max-seconds', type=int, default=300, help='短时自愈窗口(默认300)')
    parser.add_argument('--cooldown-minutes', type=int, default=5, help='已解决后冷却(默认5)')
    parser.add_argument('--lifecycle', dest='lifecycle_enabled', action='store_true', default=True, help='开启告警生命周期')
    parser.add_argument('--no-lifecycle', dest='lifecycle_enabled', action='store_false', help='关闭生命周期')
    parser.add_argument('--keep-hours', type=float, default=24.0, help='正常模拟数据保留小时数(默认24)')
    parser.add_argument('--keep-rows', type=int, default=0, help='异常数据保留最大行数，0=不限')
    args = parser.parse_args()

    _guard.ensure_dev_mode()

    interval_us = max(int(args.interval * 1_000_000), 100_000)
    print('Starting real-time sensor simulation (with alert lifecycle)...')
    print('Lifecycle: dedup / auto-resolve(%.0fmin) / transient(<=%.0fs) / cooldown(%.0fmin) / for-duration(%d)'
          % (args.auto_resolve_minutes, args.transient_max_seconds, args.cooldown_minutes, args.consecutive))
    print('Press Ctrl+C to stop')
    print()

    iteration = 0
    try:
        while True:
            iteration += 1
            tick = datetime.now()
            updated = update_sensors(
                interval_us, args.per_cycle, args.alert_prob, args.consecutive,
                args.auto_resolve_minutes, args.transient_max_seconds, args.cooldown_minutes,
                args.lifecycle_enabled,
            )
            now_s = datetime.now().strftime('%H:%M:%S.%f')[:-3]
            print('[%s] Updated %s sensors (lifecycle=%s)' % (now_s, updated, args.lifecycle_enabled), flush=True)

            if iteration % 60 == 0:
                conn = sqlite3.connect(DB_PATH, timeout=30)
                _cleanup_sensor_data(conn, args.keep_hours, args.keep_rows)
                conn.close()
                print('[%s] cleaned normal sensor_data (keep %gh)' % (datetime.now().strftime('%H:%M:%S'), args.keep_hours), flush=True)

            elapsed_us = int((datetime.now() - tick).total_seconds() * 1_000_000)
            sleep_us = interval_us - elapsed_us
            if sleep_us > 0:
                import time
                time.sleep(sleep_us / 1_000_000)
    except KeyboardInterrupt:
        print()
        print('Simulation stopped.')


if __name__ == '__main__':
    _main()
