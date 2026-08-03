import sqlite3
import os
import json
from datetime import datetime

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Check existing rules
c.execute('SELECT COUNT(*) FROM alert_rules')
existing = c.fetchone()[0]
print(f'Existing alert rules: {existing}')

if existing > 0:
    print('Rules already exist, skipping...')
    conn.close()
    exit()

# Create alert rules
rules = [
    ('温度严重过高', 'TEMP_CRITICAL', 'temperature', 'gt', 40, 'emergency', 1, '["email", "sms"]'),
    ('温度过高告警', 'TEMP_HIGH', 'temperature', 'gt', 35, 'serious', 1, '["email", "sms"]'),
    ('温度警告', 'TEMP_WARNING', 'temperature', 'gt', 30, 'general', 1, '["email"]'),
    ('温度过低告警', 'TEMP_LOW', 'temperature', 'lt', 10, 'general', 1, '["email"]'),
    ('湿度过高告警', 'HUM_HIGH', 'humidity', 'gt', 70, 'general', 1, '["email"]'),
    ('湿度过低告警', 'HUM_LOW', 'humidity', 'lt', 30, 'general', 1, '["email"]'),
    ('功率严重过载', 'POWER_CRITICAL', 'power', 'gt', 25, 'emergency', 1, '["email", "sms"]'),
    ('功率过载告警', 'POWER_OVER', 'power', 'gt', 18, 'serious', 1, '["email", "sms"]'),
    ('功率警告', 'POWER_WARNING', 'power', 'gt', 15, 'general', 1, '["email"]'),
    ('烟雾告警', 'SMOKE_ALERT', 'smoke', 'eq', 1, 'emergency', 1, '["sms"]'),
    ('门禁异常告警', 'DOOR_ALERT', 'door', 'eq', 1, 'serious', 1, '["email", "sms"]'),
    ('设备离线告警', 'DEVICE_OFFLINE', 'status', 'eq', 1, 'serious', 1, '["email"]'),
]

now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
for rule in rules:
    c.execute('''
        INSERT INTO alert_rules (name, code, metric, condition, threshold, alert_level, enabled, notify_methods, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', rule + (now, now))
    print(f'Created: {rule[0]}')

conn.commit()
c.execute('SELECT COUNT(*) FROM alert_rules')
print(f'\\nTotal rules: {c.fetchone()[0]}')

conn.close()
print('Done!')
