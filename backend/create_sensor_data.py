import sqlite3
import os
import random
from datetime import datetime, timedelta

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Fix the sensor_data table - change BIGINT to INTEGER for autoincrement
try:
    c.execute('DROP TABLE IF EXISTS sensor_data_new')
    c.execute('''
        CREATE TABLE sensor_data_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id INTEGER NOT NULL,
            value FLOAT NOT NULL,
            recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY(sensor_id) REFERENCES sensors(id) ON DELETE CASCADE
        )
    ''')
    c.execute('INSERT INTO sensor_data_new (sensor_id, value, recorded_at) SELECT sensor_id, value, recorded_at FROM sensor_data')
    c.execute('DROP TABLE sensor_data')
    c.execute('ALTER TABLE sensor_data_new RENAME TO sensor_data')
    conn.commit()
    print('Fixed sensor_data table')
except Exception as e:
    print(f'Fix error: {e}')

# Get sensors
c.execute('SELECT id, threshold_min, threshold_max, sensor_type FROM sensors')
sensors = c.fetchall()
print(f'Sensors: {len(sensors)}')

# Create historical data with explicit id
data_count = 0
base_time = datetime.now()
current_id = 1

for sensor_id, min_val, max_val, sensor_type in sensors:
    for i in range(48):
        if sensor_type == 'smoke' or sensor_type == 'door_magnetic':
            value = random.choice([0, 0, 0, 0, 1])
        else:
            value = random.uniform(min_val or 0, max_val or 100)
        
        recorded_at = base_time - timedelta(minutes=30*(47-i))
        c.execute('''
            INSERT INTO sensor_data (id, sensor_id, value, recorded_at)
            VALUES (?, ?, ?, ?)
        ''', (current_id, sensor_id, round(value, 2), recorded_at.strftime('%Y-%m-%d %H:%M:%S')))
        current_id += 1
        data_count += 1

conn.commit()
print(f'Data records created: {data_count}')

c.execute('SELECT COUNT(*) FROM sensor_data')
print(f'Total sensor data: {c.fetchone()[0]}')

conn.close()
print('Done!')
