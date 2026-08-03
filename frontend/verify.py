import requests

BASE_URL = 'http://localhost:8000/api/v1'
resp = requests.post(BASE_URL + '/auth/login', json={'username':'admin','password':'admin@123456'})
token = resp.json()['access_token']
headers = {'Authorization': 'Bearer ' + token}

# Test with rack_id 21 (should have devices now)
resp = requests.get(BASE_URL + '/devices', headers=headers, params={'page': 1, 'page_size': 5, 'rack_id': 21})
print('Status:', resp.status_code)
data = resp.json()
print('Total:', data.get('total', 0))
for d in data.get('items', [])[:3]:
    print('  -', d.get('name'), 'rack_id:', d.get('rack_id'))
