import requests

BASE_URL = 'http://localhost:8000/api/v1'
resp = requests.post(BASE_URL + '/auth/login', json={'username':'admin','password':'admin@123456'})
token = resp.json()['access_token']
headers = {'Authorization': 'Bearer ' + token}

# Get devices without rack_id
resp = requests.get(BASE_URL + '/devices', headers=headers, params={'page': 1, 'page_size': 5})
print('Devices (no filter):', resp.status_code)
data = resp.json()
print('Total:', data.get('total', 0))

items = data.get('items', [])
for d in items[:5]:
    print('  -', d.get('name'), 'rack_id:', d.get('rack_id'), 'status:', d.get('status'))
