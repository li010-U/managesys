import requests
import json

BASE_URL = 'http://localhost:8000/api/v1'
resp = requests.post(BASE_URL + '/auth/login', json={'username':'admin','password':'admin@123456'})
token = resp.json()['access_token']
headers = {'Authorization': 'Bearer ' + token}

# Check alert rules
resp = requests.get(BASE_URL + '/alerts/rules', headers=headers)
print('Alert Rules Status:', resp.status_code)
if resp.status_code == 200:
    data = resp.json()
    print('Total rules:', data.get('total', 0))
    for item in data.get('items', [])[:5]:
        print('  -', item.get('name'), '(' + item.get('code') + ')')
else:
    print('Error:', resp.text)

# Check alert stats
resp = requests.get(BASE_URL + '/alerts/stats', headers=headers)
print('\\nAlert Stats:', resp.status_code)
print(json.dumps(resp.json(), indent=2))
