import requests
import random

BASE_URL = 'http://localhost:8000/api/v1'
resp = requests.post(f'{BASE_URL}/auth/login', json={'username':'admin','password':'admin@123456'})
token = resp.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

# Create comprehensive alert rules
alert_rules = [
    # Temperature rules
    {'name': '温度严重过高', 'code': 'TEMP_CRITICAL', 'metric': 'temperature', 'condition': 'gt', 'threshold': 40, 'alert_level': 'emergency', 'enabled': True, 'notify_methods': ['email', 'sms']},
    {'name': '温度过高告警', 'code': 'TEMP_HIGH', 'metric': 'temperature', 'condition': 'gt', 'threshold': 35, 'alert_level': 'serious', 'enabled': True, 'notify_methods': ['email', 'sms']},
    {'name': '温度警告', 'code': 'TEMP_WARNING', 'metric': 'temperature', 'condition': 'gt', 'threshold': 30, 'alert_level': 'general', 'enabled': True, 'notify_methods': ['email']},
    {'name': '温度过低告警', 'code': 'TEMP_LOW', 'metric': 'temperature', 'condition': 'lt', 'threshold': 10, 'alert_level': 'general', 'enabled': True, 'notify_methods': ['email']},
    
    # Humidity rules
    {'name': '湿度过高告警', 'code': 'HUM_HIGH', 'metric': 'humidity', 'condition': 'gt', 'threshold': 70, 'alert_level': 'general', 'enabled': True, 'notify_methods': ['email']},
    {'name': '湿度过低告警', 'code': 'HUM_LOW', 'metric': 'humidity', 'condition': 'lt', 'threshold': 30, 'alert_level': 'general', 'enabled': True, 'notify_methods': ['email']},
    
    # Power rules
    {'name': '功率严重过载', 'code': 'POWER_CRITICAL', 'metric': 'power', 'condition': 'gt', 'threshold': 25, 'alert_level': 'emergency', 'enabled': True, 'notify_methods': ['email', 'sms']},
    {'name': '功率过载告警', 'code': 'POWER_OVER', 'metric': 'power', 'condition': 'gt', 'threshold': 18, 'alert_level': 'serious', 'enabled': True, 'notify_methods': ['email', 'sms']},
    {'name': '功率警告', 'code': 'POWER_WARNING', 'metric': 'power', 'condition': 'gt', 'threshold': 15, 'alert_level': 'general', 'enabled': True, 'notify_methods': ['email']},
    
    # Security rules
    {'name': '烟雾告警', 'code': 'SMOKE_ALERT', 'metric': 'smoke', 'condition': 'eq', 'threshold': 1, 'alert_level': 'emergency', 'enabled': True, 'notify_methods': ['sms']},
    {'name': '门禁异常告警', 'code': 'DOOR_ALERT', 'metric': 'door', 'condition': 'eq', 'threshold': 1, 'alert_level': 'serious', 'enabled': True, 'notify_methods': ['email', 'sms']},
    
    # Device rules
    {'name': '设备离线告警', 'code': 'DEVICE_OFFLINE', 'metric': 'status', 'condition': 'eq', 'threshold': 1, 'alert_level': 'serious', 'enabled': True, 'notify_methods': ['email']},
    {'name': '设备故障告警', 'code': 'DEVICE_FAULT', 'metric': 'status', 'condition': 'eq', 'threshold': 2, 'alert_level': 'emergency', 'enabled': True, 'notify_methods': ['email', 'sms']},
]

print('Creating alert rules...')
rules_created = 0
for rule in alert_rules:
    resp = requests.post(f'{BASE_URL}/alerts/rules', headers=headers, json=rule)
    if resp.status_code in [200, 201]:
        rules_created += 1
        print(f'  Created: {rule[\"name\"]} ({rule[\"code\"]})')
    else:
        print(f'  Failed: {rule[\"name\"]} - {resp.status_code}')

print(f'\\nTotal rules created: {rules_created}')

# Verify
resp = requests.get(f'{BASE_URL}/alerts/rules', headers=headers)
print(f'\\nTotal rules in system: {resp.json().get(\"total\", 0)}')
