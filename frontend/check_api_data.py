import requests

BASE_URL = 'http://localhost:8000/api/v1'
resp = requests.post(BASE_URL + '/auth/login', json={'username':'admin','password':'admin@123456'})
token = resp.json()['access_token']
headers = {'Authorization': 'Bearer ' + token}

# Get first 5 racks from API
resp = requests.get(BASE_URL + '/facilities/racks', headers=headers, params={'page': 1, 'page_size': 5})
racks = resp.json().get('items', [])
print('Racks from API:')
for r in racks:
    print('  ID:', r.get('id'), 'Code:', r.get('code'))

# Get all devices
resp = requests.get(BASE_URL + '/devices', headers=headers, params={'page': 1, 'page_size': 5})
devices = resp.json().get('items', [])
print('\\nFirst 5 devices:')
for d in devices:
    print('  -', d.get('name'), 'rack_id:', d.get('rack_id'))

# Check devices grouped by rack_id
from collections import defaultdict
rack_devices = defaultdict(list)
for d in devices:
    rack_devices[d.get('rack_id')].append(d.get('name'))
print('\\nDevices by rack_id:')
for rid, names in rack_devices.items():
    print('  rack_id', rid, ':', len(names), 'devices')
