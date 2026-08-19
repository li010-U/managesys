# -*- coding: utf-8 -*-
"""环境/气象数据自动轮询采集（仅限开发环境，写入会被 _guard 拦截）。

用途: 周期采集天气/温度/湿度/风速并写入 env_weather_records，供
"偶发故障-环境关联统计"使用。支持两种数据源:
  --source sim   : 本地生成"看起来像真实天气"的演示值（默认，无网络依赖）
  --source real  : 调用 Open-Meteo 开放接口(无需 API Key)拉取真实天气

安全护栏:
  1. 必须 ALLOW_DEV_TOOL_WRITE=1 才允许实际写库。
  2. 默认只打印不写库（--dry-run）。
  3. 时间戳统一按本地口径。

示例:
  ALLOW_DEV_TOOL_WRITE=1 python collect_env_weather.py --source sim --interval 300 --really-write
  ALLOW_DEV_TOOL_WRITE=1 python collect_env_weather.py --source real --lat 31.8 --lon 117.2 --once --really-write
"""
import _guard
import argparse
import os
import math
import random
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from app.core.timeutil import now_local

DB_PATH = str(Path(__file__).resolve().parents[1] / 'data' / 'managesys.db')

# Open-Meteo 开放接口（无需 API Key，适合开发/演示）
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

# 演示数据：按季节/时段生成"看似合理"的天气
WEATHERS = ['晴', '多云', '阴', '雨', '雪', '风']
_SEASON_TEMP = {'1': 5, '2': 8, '3': 14, '4': 20, '5': 25, '6': 29,
                '7': 32, '8': 31, '9': 26, '10': 20, '11': 13, '12': 7}


def _sim_weather():
    """生成一组演示值（返回 dict）。"""
    month = str(now_local().month)
    base_temp = _SEASON_TEMP.get(month, 20)
    # 一天内温度呈"午高早晚低"的正弦波动
    hour = now_local().hour
    diurnal = 4 * math.sin((hour - 9) / 24 * 2 * math.pi)
    temperature = base_temp + diurnal + random.uniform(-2, 2)
    weather = random.choices(WEATHERS, weights=[4, 3, 2, 1.5, 0.6, 1])[0]
    humidity = random.uniform(35, 85)
    if weather in ('雨', '雪'):
        humidity = random.uniform(70, 95)
    windspeed = random.uniform(1, 9)
    if weather == '风':
        windspeed = random.uniform(8, 15)
    return {
        'temperature': round(temperature, 1),
        'humidity': round(humidity, 1),
        'weather': weather,
        'windspeed': round(windspeed, 1),
    }


def _fetch_real(lat, lon):
    """调用 Open-Meteo 拉取实时天气。失败时返回 None 由调用方回退。"""
    import urllib.request
    import json
    params = (f"?latitude={lat}&longitude={lon}"
              f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m"
              f"&timezone=Asia%2FShanghai")
    url = OPEN_METEO_URL + params
    with urllib.request.urlopen(url, timeout=15) as resp:
        data = json.loads(resp.read().decode('utf-8'))
    cur = data.get('current', {})
    weather_code = cur.get('weather_code', 1)
    # WMO weather code -> 中文天气
    mapping = {0: '晴', 1: '晴', 2: '多云', 3: '阴', 45: '雾', 48: '雾',
               51: '雨', 53: '雨', 55: '雨', 61: '雨', 63: '雨', 65: '雨',
               71: '雪', 73: '雪', 75: '雪', 80: '雨', 81: '雨', 82: '雨',
               95: '雨', 96: '雨', 99: '雨'}
    return {
        'temperature': cur.get('temperature_2m'),
        'humidity': cur.get('relative_humidity_2m'),
        'weather': mapping.get(weather_code, '多云'),
        'windspeed': cur.get('wind_speed_10m'),
    }


def _collect_one(source, lat, lon):
    if source == 'real':
        data = _fetch_real(lat, lon)
        if data is None:
            print('[warn] 拉取真实天气失败，回退到演示值')
            data = _sim_weather()
    else:
        data = _sim_weather()
    return data


def _insert(conn, data, location_id, location_name):
    now = now_local().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute(
        "INSERT INTO env_weather_records "
        "(location_id, location_name, temperature, humidity, weather, windspeed, recorded_at, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (location_id, location_name, data['temperature'], data['humidity'],
         data['weather'], data['windspeed'], now, now)
    )
    conn.commit()


def _main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--source', choices=['sim', 'real'], default='sim', help='数据源: sim=演示, real=Open-Meteo')
    parser.add_argument('--interval', type=int, default=300, help='轮询间隔（秒，默认 300）')
    parser.add_argument('--once', action='store_true', help='只采集一次后退出')
    parser.add_argument('--location-id', type=int, default=None, help='位置ID(机房/数据中心ID)，可空')
    parser.add_argument('--location-name', default='主机房', help='位置名称，默认 主机房')
    parser.add_argument('--lat', type=float, default=31.82, help='纬度(real 源)，默认合肥')
    parser.add_argument('--lon', type=float, default=117.23, help='经度(real 源)，默认合肥')
    parser.add_argument('--dry-run', action='store_true', help='只打印不写库（默认 dry-run）')
    parser.add_argument('--really-write', action='store_true', help='真正写库（仍需 ALLOW_DEV_TOOL_WRITE=1）')
    args = parser.parse_args()

    if not (args.dry_run or args.really_write):
        print('[!] 请明确指定 --dry-run（仅预览）或 --really-write（实际写库）。')
        sys.exit(2)
    if not args.dry_run:
        _guard.ensure_dev_mode()

    print(f"环境采集工具: source={args.source}, interval={args.interval}s, location={args.location_name}")
    try:
        while True:
            data = _collect_one(args.source, args.lat, args.lon)
            line = (f"  [{now_local().strftime('%H:%M:%S')}] {data['weather']} "
                    f"{data['temperature']}°C / {data['humidity']}%RH / {data['windspeed']}m/s")
            print(line)
            if args.dry_run:
                print('    (dry-run，未写库)')
            else:
                conn = sqlite3.connect(DB_PATH)
                try:
                    _insert(conn, data, args.location_id, args.location_name)
                finally:
                    conn.close()
            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print('\n[info] 已停止环境采集。')
        sys.exit(0)


if __name__ == '__main__':
    _main()
