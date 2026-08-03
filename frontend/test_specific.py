import requests

BASE_URL = 'http://localhost:8000/api/v1'
resp = requests.post(BASE_URL + '/auth/login', json={'username':'admin','password':'admin@123456'})
token = resp.json()['access_token']
headers = {'Authorization': 'Bearer ' + token}

# Get device for rack_id 40 (which should show in the grid)
rack_id = 40
resp = requests.get(BASE_URL + '/devices', headers=headers, params={'page': 1, 'page_size': 10, 'rack_id': rack_id})
print('Status for rack_id', rack_id, ':', resp.status_code)
print('Total:', resp.json().get('total', 0))

# Check if rack 40 is in the rack list
resp = requests.get(BASE_URL + '/facilities/racks', headers=headers, params={'page': 1, 'page_size': 20})
racks = resp.json().get('items', [])
for r in racks:
    if r.get('id') == rack_id:
        print('Found rack:', r.get('code'), 'row_pos:', r.get('row_pos'), 'col_pos:', r.get('col_pos'))
        break
