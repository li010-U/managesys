import sqlite3
import os
import random
import json
from datetime import datetime

db_path = os.path.join(os.path.dirname(__file__), 'data', 'managesys.db')

def update_sensors():
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Get all sensors
    c.execute('SELECT id, code, sensor_type, threshold_min, threshold_max, alert_level FROM sensors')
    sensors = c.fetchall()
    
    # Update 5-10 random sensors each time
    update_count = random.randint(5, min(10, len(sensors)))
    selected = random.sample(sensors, update_count)
    
    alerts_created = 0
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Get max alert id
    c.execute('SELECT COALESCE(MAX(id), 0) FROM alerts')
    max_alert_id = c.fetchone()[0]
    
    for sensor_id, code, sensor_type, min_val, max_val, alert_level in selected:
        # Generate new value
        if sensor_type in ['smoke', 'door_magnetic']:
            value = random.choice([0, 0, 0, 1])
            json_value = f'{{"value": {value}, "unit": ""}}'
            threshold = max_val * 0.8 if max_val else 0.5
            is_alert = value >= threshold and threshold > 0
        else:
            center = (min_val + max_val) / 2 if max_val and min_val else 50
            value = random.gauss(center, (max_val - min_val) / 4 if max_val and min_val else 20)
            value = max(min_val or 0, min(max_val or 100, value))
            unit = 'C' if sensor_type == 'temperature' else '%' if sensor_type == 'humidity' else 'kW'
            json_value = f'{{"value": {round(value, 2)}, "unit": "{unit}"}}'
            threshold = max_val * 0.85 if max_val else 100
            is_alert = value > threshold
        
        # Update sensor
        c.execute('''
            UPDATE sensors SET current_value=?, last_update_time=?, status='online' WHERE id=?
        ''', (json_value, now, sensor_id))
        
        # Insert sensor data
        c.execute('''
            INSERT INTO sensor_data (sensor_id, value, recorded_at)
            VALUES (?, ?, ?)
        ''', (sensor_id, round(value, 2), now))
        
        # Create alert if needed
        if is_alert and random.random() < 0.3:
            max_alert_id += 1
            c.execute('''
                INSERT INTO alerts (id, target_type, target_id, title, description, level, status, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (max_alert_id, 'sensor', str(sensor_id),
                  f'{sensor_type} 监测值异常',
                  f'当前值: {round(value, 2)}, 阈值: {threshold:.2f}',
                  alert_level, 'new', 'monitor', now))
            alerts_created += 1
    
    conn.commit()
    conn.close()
    return update_count, alerts_created

if __name__ == '__main__':
    import time
    print('Starting real-time sensor simulation...')
    print('Press Ctrl+C to stop')
    print()
    
    iteration = 0
    try:
        while True:
            iteration += 1
            sensors_updated, alerts_created = update_sensors()
            timestamp = datetime.now().strftime('%H:%M:%S')
            print(f'[{timestamp}] Updated {sensors_updated} sensors', end='')
            if alerts_created > 0:
                print(f' | Created {alerts_created} alerts', end='')
            print()
            
            if iteration % 1000 == 0:
                conn = sqlite3.connect(db_path)
                c = conn.cursor()
                c.execute('''
                    DELETE FROM sensor_data 
                    WHERE id NOT IN (SELECT id FROM sensor_data ORDER BY recorded_at DESC LIMIT 10000)
                ''')
                conn.commit()
                conn.close()
                print('Cleaned up old sensor data')
            
            time.sleep(5)
    except KeyboardInterrupt:
        print('\\nSimulation stopped.')
