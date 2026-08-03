import requests

BASE_URL = 'http://localhost:8000/api/v1'
resp = requests.post(BASE_URL + '/auth/login', json={'username':'admin','password':'admin@123456'})
token = resp.json()['access_token']
headers = {'Authorization': 'Bearer ' + token}

# Get first rack
resp = requests.get(BASE_URL + '/facilities/racks', headers=headers, params={'page': 1, 'page_size': 3})
racks = resp.json().get('items', [])
print('First 3 racks:')
for r in racks:
    print('  ID:', r.get('id'), 'Code:', r.get('code'))

if racks:
    rack_id = racks[0]['id']
    print('\\nTesting rack_id:', rack_id)
    
    # Test with integer rack_id
    resp = requests.get(BASE_URL + '/devices', headers=headers, params={'page': 1, 'page_size': 10, 'rack_id': rack_id})
    print('Status:', resp.status_code)
    print('Response:', resp.text[:500])
