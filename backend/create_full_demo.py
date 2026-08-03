"""生成完整的模拟数据"""
import requests
import random
from datetime import datetime, timedelta

BASE_URL = 'http://localhost:8000/api/v1'

resp = requests.post(f'{BASE_URL}/auth/login', json={'username':'admin','password':'admin@123456'})
token = resp.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

def get_items(resp):
    if 'items' in resp.json():
        return resp.json()['items']
    return resp.json().get('data', [])

def create_rooms():
    resp = requests.get(f'{BASE_URL}/facilities/data-centers', headers=headers)
    dcs = get_items(resp)
    if len(dcs) < 3:
        dcs_data = [
            {'name': '北京主数据中心', 'code': 'DC-BJ-01', 'address': '北京市海淀区中关村大街1号', 'description': '华北区域核心数据中心', 'status': 'active'},
            {'name': '上海备数据中心', 'code': 'DC-SH-01', 'address': '上海市浦东新区张江高科技园区', 'description': '华东区域灾备中心', 'status': 'active'},
            {'name': '深圳边缘数据中心', 'code': 'DC-SZ-01', 'address': '深圳市南山区科技园南区', 'description': '华南区域边缘计算节点', 'status': 'active'},
        ]
        for dc in dcs_data:
            requests.post(f'{BASE_URL}/facilities/data-centers', headers=headers, json=dc)
        resp = requests.get(f'{BASE_URL}/facilities/data-centers', headers=headers)
        dcs = get_items(resp)
    
    resp = requests.get(f'{BASE_URL}/facilities/rooms', headers=headers)
    rooms = get_items(resp)
    if len(rooms) < 10:
        for dc in dcs:
            for i in range(random.randint(3, 5)):
                room = {
                    'data_center_id': dc['id'],
                    'name': dc['name'] + ' ' + chr(65+i) + '区',
                    'code': 'RM-' + dc['code'].split('-')[-1] + '-' + str(i+1).zfill(2),
                    'floor': str(random.randint(1,6)) + '楼',
                    'area': random.randint(200, 600),
                    'load_rating': random.randint(8, 25) * 1000,
                    'tier_level': random.choice(['Tier I', 'Tier II', 'Tier III', 'Tier IV']),
                    'description': '高性能计算机房',
                    'status': 'active'
                }
                requests.post(f'{BASE_URL}/facilities/rooms', headers=headers, json=room)
        resp = requests.get(f'{BASE_URL}/facilities/rooms', headers=headers)
        rooms = get_items(resp)
    return rooms

def create_racks(rooms):
    resp = requests.get(f'{BASE_URL}/facilities/racks', headers=headers)
    racks = get_items(resp)
    if len(racks) < 30:
        for room in rooms:
            for i in range(random.randint(15, 35)):
                rack = {
                    'room_id': room['id'],
                    'name': 'A-' + str(i+1).zfill(2),
                    'code': 'RK-' + room['code'] + '-' + str(i+1).zfill(2),
                    'total_u': random.choice([42, 48]),
                    'used_u': random.randint(15, 38),
                    'max_power': random.choice([10, 15, 20, 30]),
                    'current_power': round(random.uniform(3, 18), 2),
                    'description': '标准42U机柜',
                    'status': 'active'
                }
                requests.post(f'{BASE_URL}/facilities/racks', headers=headers, json=rack)
        resp = requests.get(f'{BASE_URL}/facilities/racks', headers=headers)
        racks = get_items(resp)
    return racks

def create_device_types():
    resp = requests.get(f'{BASE_URL}/devices/types/all', headers=headers)
    types = resp.json()
    if len(types) < 6:
        types_data = [
            {'name': '服务器', 'code': 'SERVER', 'description': '标准X86服务器', 'default_height': 2, 'icon': 'server'},
            {'name': '网络设备', 'code': 'NETWORK', 'description': '交换机路由器', 'default_height': 1, 'icon': 'router'},
            {'name': '存储设备', 'code': 'STORAGE', 'description': 'SAN/NAS存储', 'default_height': 4, 'icon': 'database'},
            {'name': '安全设备', 'code': 'SECURITY', 'description': '防火墙/IDS/IPS', 'default_height': 1, 'icon': 'shield'},
            {'name': 'UPS', 'code': 'UPS', 'description': '不间断电源', 'default_height': 4, 'icon': 'battery'},
            {'name': '精密空调', 'code': 'AC', 'description': '机房精密空调', 'default_height': 4, 'icon': 'thermometer'},
        ]
        for t in types_data:
            requests.post(f'{BASE_URL}/devices/types', headers=headers, json=t)
        resp = requests.get(f'{BASE_URL}/devices/types/all', headers=headers)
        types = resp.json()
    return types

def create_devices(racks, types):
    resp = requests.get(f'{BASE_URL}/devices', headers=headers, params={'page': 1, 'page_size': 1})
    if resp.json().get('total', 0) >= 50:
        return
    brands = {'SERVER': ['Dell', 'HP', 'Lenovo', 'Huawei', 'Inspur'], 
              'NETWORK': ['Cisco', 'H3C', 'Arista', 'Juniper', 'Huawei'],
              'STORAGE': ['EMC', 'HDS', 'NetApp', 'IBM', 'Huawei'],
              'SECURITY': ['Fortinet', 'Palo Alto', 'Cisco', 'Hillstone', 'H3C'],
              'UPS': ['APC', 'Emerson', 'Schneider', 'Eaton', 'Huawei'],
              'AC': ['Emerson', 'Schneider', 'Liebert', 'Huawei', 'Evapco']}
    for rack in racks[:30]:
        for i in range(random.randint(3, 8)):
            dev_type = random.choice([t for t in types if t['code'] != 'UPS' and t['code'] != 'AC'])
            device = {
                'device_type_id': dev_type['id'],
                'rack_id': rack['id'],
                'name': dev_type['name'] + '-' + str(random.randint(1000,9999)),
                'asset_number': 'ASSET-' + str(random.randint(100000,999999)),
                'serial_number': 'SN-' + str(random.randint(10000000,99999999)),
                'brand': random.choice(brands.get(dev_type['code'], ['Generic'])),
                'model': dev_type['code'] + '-' + str(random.randint(1000,9999)),
                'cpu_info': random.choice(['Intel Xeon Gold 6248', 'Intel Xeon Silver 4214R', 'AMD EPYC 7543']),
                'memory_info': str(random.choice([32, 64, 128, 256, 512])) + 'GB DDR4',
                'disk_info': random.choice(['480GB SSD', '960GB SSD', '2TB HDD', '4TB NVMe']),
                'network_info': random.choice(['4x1GbE', '2x10GbE', '4x10GbE']),
                'purchase_date': (datetime.now() - timedelta(days=random.randint(30,1095))).strftime('%Y-%m-%d'),
                'vendor': random.choice(['总代理A公司', '集成商B公司', '原厂直供']),
                'purchase_price': round(random.uniform(15000, 800000), 2),
                'warranty_end': (datetime.now() + timedelta(days=random.randint(30,1460))).strftime('%Y-%m-%d'),
                'start_u': random.randint(1, 30),
                'end_u': random.randint(5, 40),
                'management_ip': '10.' + str(random.randint(0,255)) + '.' + str(random.randint(0,255)) + '.' + str(random.randint(1,254)),
                'business_ip': '192.168.' + str(random.randint(0,255)) + '.' + str(random.randint(1,254)),
                'mac_address': ':'.join([f'{random.randint(0,255):02x}' for _ in range(6)]),
                'status': random.choice(['online', 'online', 'online', 'online', 'offline', 'maintenance'])
            }
            requests.post(f'{BASE_URL}/devices', headers=headers, json=device)

def create_alerts():
    alert_titles = ['温度过高', 'CPU使用率过高', '内存使用率过高', '磁盘空间不足', '网络连接中断', '电源故障', '烟雾探测报警']
    for _ in range(25):
        alert = {
            'target_type': 'device',
            'target_id': str(random.randint(1, 100)),
            'title': random.choice(alert_titles),
            'description': '系统自动检测到异常，请及时处理',
            'level': random.choice(['general', 'serious', 'emergency']),
            'status': random.choice(['new', 'new', 'acknowledged', 'resolved', 'ignored']),
            'source': random.choice(['sensor', 'monitor', 'system']),
            'created_at': (datetime.now() - timedelta(hours=random.randint(0, 168))).isoformat()
        }
        requests.post(f'{BASE_URL}/alerts', headers=headers, json=alert)

if __name__ == '__main__':
    print('=' * 50)
    print('开始生成完整模拟数据...')
    print('=' * 50)
    
    rooms = create_rooms()
    print(f'机房: {len(rooms)}个')
    
    racks = create_racks(rooms)
    print(f'机柜: {len(racks)}个')
    
    types = create_device_types()
    print(f'设备类型: {len(types)}种')
    
    create_devices(racks, types)
    resp = requests.get(f'{BASE_URL}/devices', headers=headers, params={'page': 1, 'page_size': 1})
    print(f'设备: {resp.json().get("total", 0)}台')
    
    create_alerts()
    print('告警: 25条')
    
    print('=' * 50)
    print('数据生成完成!')
    print('=' * 50)
