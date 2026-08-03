import sqlite3
import os
import random
from datetime import datetime, timedelta

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Insert devices
brands = {'SERVER': ['Dell', 'HP', 'Lenovo', 'Huawei'], 
          'NETWORK': ['Cisco', 'H3C', 'Arista'],
          'STORAGE': ['EMC', 'HDS', 'NetApp'],
          'SECURITY': ['Fortinet', 'Palo Alto', 'Cisco'],
          'UPS': ['APC', 'Emerson', 'Schneider'],
          'AC': ['艾默生', 'Schneider', 'Liebert']}

c.execute('SELECT id, code FROM device_types')
type_map = {code: id for id, code in c.fetchall()}

c.execute('SELECT id FROM racks LIMIT 20')
racks = [r[0] for r in c.fetchall()]

device_count = 0
for rack_id in racks:
    for i in range(random.randint(4, 10)):
        dev_code = random.choice(list(type_map.keys()))
        brand = random.choice(brands.get(dev_code, ['Generic']))
        device = (
            type_map[dev_code], rack_id,
            f'{dev_code}-{random.randint(1000,9999)}',
            f'ASSET-{random.randint(100000,999999)}',
            f'SN-{random.randint(10000000,99999999)}',
            brand,
            f'{brand}-{random.randint(1000,9999)}',
            random.choice(['Intel Xeon Gold 6248', 'Intel Xeon Silver 4214R', 'AMD EPYC 7543']),
            f'{random.choice([32, 64, 128, 256])}GB DDR4',
            random.choice(['480GB SSD', '960GB SSD', '2TB HDD', '4TB NVMe']),
            random.choice(['4x1GbE', '2x10GbE', '4x10GbE']),
            (datetime.now() - timedelta(days=random.randint(30, 730))).strftime('%Y-%m-%d'),
            random.choice(['总代理', '集成商']),
            round(random.uniform(15000, 500000), 2),
            (datetime.now() - timedelta(days=random.randint(0, 365))).strftime('%Y-%m-%d'),
            (datetime.now() + timedelta(days=random.randint(30, 1095))).strftime('%Y-%m-%d'),
            random.randint(1, 30), random.randint(5, 40),
            f'10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}',
            f'192.168.{random.randint(0,255)}.{random.randint(1,254)}',
            ':'.join([f'{random.randint(0,255):02x}' for _ in range(6)]),
            random.choice(['online', 'online', 'online', 'offline', 'maintenance'])
        )
        try:
            c.execute('''
                INSERT INTO devices (device_type_id, rack_id, name, asset_number, serial_number,
                    brand, model, cpu_info, memory_info, disk_info, network_info,
                    purchase_date, vendor, purchase_price, warranty_start, warranty_end,
                    start_u, end_u, management_ip, business_ip, mac_address, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', device)
            device_count += 1
        except Exception as e:
            print(f'Error: {e}')

conn.commit()
c.execute('SELECT COUNT(*) FROM devices')
print(f'Devices: {c.fetchone()[0]}')

# Insert alerts
alert_titles = ['温度过高', 'CPU使用率过高', '内存使用率过高', '磁盘空间不足', '网络连接中断', '电源故障', '烟雾探测报警']
for i in range(30):
    created_at = (datetime.now() - timedelta(hours=random.randint(0, 168))).strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO alerts (target_id, title, description, level, status, source, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (
        f'device_{random.randint(1,100)}',
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
print('\\nDemo data created successfully!')
