import sqlite3
import os
import random
from datetime import datetime, timedelta

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute('SELECT id, name, code FROM rooms')
rooms = c.fetchall()
print(f'Rooms: {len(rooms)}')

c.execute('SELECT COUNT(*) FROM sensors')
existing = c.fetchone()[0]
print(f'Existing sensors: {existing}')

if existing > 0:
    print('Sensors already exist, skipping...')
    conn.close()
    exit()

sensor_configs = [
    ('temperature', 'temperature', '温度', -40, 80, 'C'),
    ('humidity', 'humidity', '湿度', 0, 100, '%'),
    ('power', 'power', '功率', 0, 30, 'kW'),
    ('smoke', 'smoke', '烟雾', 0, 1, ''),
    ('door', 'door_magnetic', '门磁', 0, 1, ''),
]

sensors_created = 0
alert_levels = ['general', 'general', 'serious', 'emergency']

for room_id, room_name, room_code in rooms:
    for i in range(random.randint(3, 5)):
        sensor_type, scode, sname, min_val, max_val, unit = random.choice(sensor_configs)
        
        full_name = room_name + '-' + sname + '-' + str(i+1)
        full_code = 'SEN-' + room_code.split('-')[1] + '-' + scode[:3].upper() + '-' + str(i+1).zfill(2)
        
        # Ensure unique code
        base_code = full_code
        counter = 1
        while True:
            c.execute('SELECT COUNT(*) FROM sensors WHERE code=?', (full_code,))
            if c.fetchone()[0] == 0:
                break
            full_code = base_code + '-' + str(counter)
            counter += 1
        
        if scode == 'smoke' or scode == 'door_magnetic':
            current_value = random.choice([0, 0, 0, 1])
        else:
            current_value = random.uniform(min_val + 5, max_val - 5)
        
        c.execute('''
            INSERT INTO sensors (room_id, name, code, sensor_type, install_position, status, current_value, 
                               threshold_min, threshold_max, alert_level, last_update_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (room_id, full_name, full_code, sensor_type,
              random.choice(['机柜顶部', '机柜中部', '机柜底部', '房间角落', '房间中央']),
              'online' if random.random() > 0.1 else 'offline',
              f'{{"value": {round(current_value, 2)}, "unit": "{unit}"}}',
              min_val, max_val, random.choice(alert_levels),
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        sensors_created += 1

conn.commit()
print(f'Sensors created: {sensors_created}')

# Create historical data
c.execute('SELECT id, threshold_min, threshold_max, sensor_type FROM sensors')
sensors = c.fetchall()
print(f'Creating historical data for {len(sensors)} sensors...')

sensor_data_count = 0
base_time = datetime.now()

for sensor_id, min_val, max_val, sensor_type in sensors:
    for i in range(48):
        if sensor_type == 'smoke' or sensor_type == 'door_magnetic':
            value = random.choice([0, 0, 0, 0, 1])
        else:
            value = random.uniform(min_val or 0, max_val or 100)
        
        recorded_at = base_time - timedelta(minutes=30*(47-i))
        c.execute('''
            INSERT INTO sensor_data (sensor_id, value, recorded_at)
            VALUES (?, ?, ?)
        ''', (sensor_id, round(value, 2), recorded_at.strftime('%Y-%m-%d %H:%M:%S')))
        sensor_data_count += 1

conn.commit()
print(f'Sensor data records: {sensor_data_count}')

c.execute('SELECT COUNT(*) FROM sensors')
print(f'Total sensors: {c.fetchone()[0]}')
c.execute('SELECT COUNT(*) FROM sensor_data')
print(f'Total sensor data: {c.fetchone()[0]}')

conn.close()
print('Done!')
