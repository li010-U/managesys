# -*- coding: utf-8 -*-
"""偶发故障-环境关联数据生成 + 可视化报表。

作用（仅开发/演示，写库会被 _guard 拦截）：
  1. 回填 env_weather_records（最近 30 天，每 30 分钟一条，贴近真实天气的演示值）。
  2. 生成一批 realistic 的偶发故障事件(transient_failure_events)，并让它们在
     高温/高湿/大风/降雨等"不利天气"时段更集中，从而让关联统计呈现相关性。
  3. 通过 AlertCorrelationReportService 生成可独立打开的 HTML 报表。

用法:
  ALLOW_DEV_TOOL_WRITE=1 python seed_correlation.py --days 30 --events 400 --report
"""
import _guard
import argparse
import os
import math
import random
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from app.core.timeutil import now_local

DB_PATH = str(Path(__file__).resolve().parents[1] / 'data' / 'managesys.db')

_WEATHERS = ['晴', '多云', '阴', '雨', '雪', '风']
_SEASON_TEMP = {'1': 5, '2': 8, '3': 14, '4': 20, '5': 25, '6': 29,
                '7': 32, '8': 31, '9': 26, '10': 20, '11': 13, '12': 7}
# 不利天气 -> 偶发故障加成（倍数）
_ADVERSE = {'雨': 1.8, '雪': 1.6, '风': 2.2, '阴': 1.2, '多云': 1.0, '晴': 0.6}


def _sim_values(at: datetime) -> dict:
    month = str(at.month)
    base = _SEASON_TEMP.get(month, 20)
    diurnal = 4 * math.sin((at.hour - 9) / 24 * 2 * math.pi)
    temperature = base + diurnal + random.uniform(-2, 2)
    weather = random.choices(_WEATHERS, weights=[4, 3, 2, 1.5, 0.6, 1])[0]
    humidity = random.uniform(35, 85)
    if weather in ('雨', '雪'):
        humidity = random.uniform(70, 95)
    windspeed = random.uniform(1, 9) if weather != '风' else random.uniform(8, 15)
    return {
        'temperature': round(temperature, 1),
        'humidity': round(humidity, 1),
        'weather': weather,
        'windspeed': round(windspeed, 1),
        'recorded_at': at,
    }


def seed_env(conn, days: int) -> int:
    """每 30 分钟回填一条 env_weather_records（防止重复，按时间戳去重）。"""
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM env_weather_records")
    if c.fetchone()[0] > 0:
        print("env_weather_records 已有数据，跳过回填。")
        return 0
    now = now_local()
    start = now - timedelta(days=days)
    step = timedelta(minutes=30)
    t = start
    inserted = 0
    while t <= now:
        v = _sim_values(t)
        c.execute(
            "INSERT INTO env_weather_records (location_id, location_name, temperature, humidity, weather, windspeed, recorded_at, created_at) "
            "VALUES (0, '主机房', ?, ?, ?, ?, ?, ?)",
            (v['temperature'], v['humidity'], v['weather'], v['windspeed'],
             v['recorded_at'].strftime('%Y-%m-%d %H:%M:%S.%f'), datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')),
        )
        inserted += 1
        t += step
    conn.commit()
    return inserted


def seed_transient(conn, days: int, count: int) -> int:
    """生成 count 条偶发故障事件，让其在不利天气时段更集中，并附着环境快照。"""
    c = conn.cursor()
    # 读取回填的环境记录（按时间）
    envs = c.execute(
        "SELECT temperature, humidity, weather, windspeed, recorded_at FROM env_weather_records ORDER BY recorded_at"
    ).fetchall()
    if not envs:
        print("env_weather_records 为空，先生成环境数据。")
        return 0

    env_by_idx = envs  # [(temp, hum, weather, wind, ts)]
    now = now_local()
    start = now - timedelta(days=days)
    # 采样时间点
    times = [start + timedelta(minutes=int(random.random() * days * 1440)) for _ in range(count)]
    times.sort()
    # 最近邻环境
    def nearest_env(ts):
        best = envs[0]
        best_d = abs((_parse_ts(best[4]) - ts).total_seconds())
        for e in envs:
            d = abs((_parse_ts(e[4]) - ts).total_seconds())
            if d < best_d:
                best, best_d = e, d
        return best

    inserted = 0
    i = 0
    ei = 0
    for ts in times:
        e = nearest_env(ts)
        (temp, hum, weather, wind, rts) = e
        # 依据天气/温湿/风速加权决定是否"生成"（体现相关性）
        adverse = _ADVERSE.get(weather, 1.0)
        hot = 1.6 if (temp or 0) >= 33 else 1.0
        humid = 1.5 if (hum or 0) >= 75 else 1.0
        windy = 1.4 if (wind or 0) >= 8 else 1.0
        w = adverse * hot * humid * windy
        if random.random() > w / 4.5:
            continue
        start_dt = ts
        duration = random.randint(2, 300)
        rec = ts + timedelta(seconds=duration)
        c.execute(
            "INSERT INTO transient_failure_events "
            "(alert_id, target_type, target_id, metric, title, started_at, recovered_at, duration_seconds, "
            " env_temperature, env_humidity, env_weather, env_windspeed, location_id, location_name, created_at) "
            "VALUES (NULL, 'sensor', ?, NULL, '偶发故障(环境关联)', ?, ?, ?, ?, ?, ?, ?, 0, '主机房', ?)",
            (str(1000 + i), start_dt.strftime('%Y-%m-%d %H:%M:%S.%f'),
             rec.strftime('%Y-%m-%d %H:%M:%S.%f'), int(duration),
             temp, hum, weather, wind, datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')),
        )
        i += 1
        inserted += 1
    conn.commit()
    return inserted


def _parse_ts(s):
    try:
        return datetime.strptime(s, '%Y-%m-%d %H:%M:%S.%f')
    except ValueError:
        return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')


def _main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--days', type=int, default=30)
    parser.add_argument('--events', type=int, default=400)
    parser.add_argument('--report', action='store_true', help='生成 HTML 可视化报表')
    parser.add_argument('--out', default='', help='HTML 报表输出路径(默认 reports/alert_correlation_report.html)')
    args = parser.parse_args()
    _guard.ensure_dev_mode()

    conn = sqlite3.connect(DB_PATH, timeout=30)
    n_env = seed_env(conn, args.days)
    print('环境数据回填: %d 条' % n_env)
    n_tr = seed_transient(conn, args.days, args.events)
    print('偶发故障事件生成: %d 条' % n_tr)
    conn.close()

    if args.report:
        import asyncio
        from pathlib import Path
        script_root = Path(__file__).resolve().parents[1]
        out_path = args.out or (str(script_root.parent / 'reports' / 'alert_correlation_report.html'))
        # 使用应用 async 引擎生成报表
        from app.db.session import async_session_factory
        from app.services.alert_report_service import AlertCorrelationReportService

        async def gen():
            async with async_session_factory() as db:
                svc = AlertCorrelationReportService(db)
                data = await svc.build(days=args.days)
                html = svc.render_html(data)
                Path(out_path).write_text(html, encoding='utf-8')
                return data

        data = asyncio.run(gen())
        print('HTML 报表已生成: %s' % out_path)
        print('偶发故障总数: %s 平均时长: %ss' % (data['summary']['count'], data['summary']['avg_duration_seconds']))


if __name__ == '__main__':
    _main()
