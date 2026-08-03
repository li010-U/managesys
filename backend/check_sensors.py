import sqlite3
import os
from datetime import datetime

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')
conn = sqlite3.connect(db_path)
c = conn.cursor()

# Check latest sensor data
c.execute('''
    SELECT s.name, s.current_value, s.last_update_time 
    FROM sensors s 
    ORDER BY s.last_update_time DESC 
    LIMIT 5
''')
print('Latest sensor updates:')
for row in c.fetchall():
    print(f'  {row[0]}: {row[1]} at {row[2]}')

# Check sensor data count
c.execute('SELECT COUNT(*) FROM sensor_data')
print(f'\\nTotal sensor data records: {c.fetchone()[0]}')

# Check latest records
c.execute('SELECT sensor_id, value, recorded_at FROM sensor_data ORDER BY recorded_at DESC LIMIT 5')
print('\\nLatest sensor data:')
for row in c.fetchall():
    print(f'  Sensor {row[0]}: {row[1]} at {row[2]}')

# Check alerts
c.execute('SELECT COUNT(*) FROM alerts')
print(f'\\nTotal alerts: {c.fetchone()[0]}')

conn.close()
