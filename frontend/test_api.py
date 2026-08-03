import requests

BASE_URL = 'http://localhost:8000/api/v1'
resp = requests.post(BASE_URL + '/auth/login', json={'username':'admin','password':'admin@123456'})
token = resp.json()['access_token']
headers = {'Authorization': 'Bearer ' + token}

# Get racks
resp = requests.get(BASE_URL + '/facilities/racks', headers=headers, params={'page': 1, 'page_size': 5})
racks = resp.json().get('items', [])
print('Racks:', len(racks))

# Get devices with rack_id
resp = requests.get(BASE_URL + '/devices', headers=headers, params={'page': 1, 'page_size': 999, 'rack_id': 1})
print('Devices status:', resp.status_code)
data = resp.json()
print('Total devices:', data.get('total', 0))

items = data.get('items', [])
for d in items[:5]:
    print('  -', d.get('name'), 'rack_id:', d.get('rack_id'))
