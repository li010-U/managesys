import sqlite3
import os
import random
from datetime import datetime, timedelta

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Insert alerts with explicit id starting from 1
alert_titles = ['温度过高', 'CPU使用率过高', '内存使用率过高', '磁盘空间不足', '网络连接中断', '电源故障', '烟雾探测报警']
c.execute('SELECT MAX(id) FROM alerts')
max_id = c.fetchone()[0] or 0

for i in range(30):
    max_id += 1
    created_at = (datetime.now() - timedelta(hours=random.randint(0, 168))).strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO alerts (id, target_type, target_id, title, description, level, status, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        max_id,
        'device',
        f'device_{random.randint(1,50)}',
        random.choice(alert_titles),
        '系统自动检测到异常，请及时处理',
        random.choice(['general', 'serious', 'emergency']),
        random.choice(['new', 'new', 'acknowledged', 'resolved']),
        'monitor',
        created_at
    ))
conn.commit()
c.execute('SELECT COUNT(*) FROM alerts')
print(f'Alerts: {c.fetchone()[0]}')

conn.close()
print('Done!')
