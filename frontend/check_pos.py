import requests

BASE_URL = 'http://localhost:8000/api/v1'
resp = requests.post(BASE_URL + '/auth/login', json={'username':'admin','password':'admin@123456'})
token = resp.json()['access_token']
headers = {'Authorization': 'Bearer ' + token}

# Get racks and show row_pos/col_pos
resp = requests.get(BASE_URL + '/facilities/racks', headers=headers, params={'page': 1, 'page_size': 10})
racks = resp.json().get('items', [])
print('First 10 racks with positions:')
for r in racks:
    print('  ID:', r.get('id'), 'Code:', r.get('code'), 'row_pos:', r.get('row_pos'), 'col_pos:', r.get('col_pos'))
