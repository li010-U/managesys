"""模拟实时监控数据更新"""
import requests
import random
import time
from datetime import datetime

BASE_URL = 'http://localhost:8000/api/v1'

def get_token():
    resp = requests.post(f'{BASE_URL}/auth/login', json={'username':'admin','password':'admin@123456'})
    return resp.json()['access_token']

def get_sensors(token):
    headers = {'Authorization': f'Bearer {token}'}
    resp = requests.get(f'{BASE_URL}/sensors/all', headers=headers)
    if resp.status_code == 200:
        return resp.json().get('data', [])
    return []

def update_sensor_value(token, sensor_id, value):
    headers = {'Authorization': f'Bearer {token}'}
    resp = requests.put(f'{BASE_URL}/sensors/{sensor_id}', headers=headers, json={
        'current_value': {'value': round(value, 2), 'unit': 'C'},
        'status': 'online',
        'last_update_time': datetime.now().isoformat()
    })
    return resp.status_code == 200

def generate_alert(token, sensor_id, value, threshold):
    headers = {'Authorization': f'Bearer {token}'}
    if value > threshold:
        resp = requests.post(f'{BASE_URL}/alerts', headers=headers, json={
            'target_type': 'sensor',
            'target_id': str(sensor_id),
            'title': f'传感器 {sensor_id} 数值异常',
            'description': f'当前值 {value:.2f} 超过阈值 {threshold}',
            'level': 'general',
            'source': 'monitor'
        })
        return True
    return False

if __name__ == '__main__':
    print('Starting simulation...')
    token = get_token()
    print(f'Logged in')
    
    while True:
        sensors = get_sensors(token)
        if not sensors:
            print('No sensors found')
            time.sleep(10)
            continue
        
        for sensor in random.sample(sensors, min(5, len(sensors))):
            new_value = random.uniform(sensor.get('threshold_min', 0), sensor.get('threshold_max', 100))
            update_sensor_value(token, sensor['id'], new_value)
            generate_alert(token, sensor['id'], new_value, sensor.get('threshold_max', 100) * 0.8)
        
        print(f'{datetime.now().strftime("%H:%M:%S")} - Updated {min(5, len(sensors))} sensors')
        time.sleep(5)
