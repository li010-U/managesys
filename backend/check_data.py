import requests
BASE_URL = 'http://localhost:8000/api/v1'
resp = requests.post(f'{BASE_URL}/auth/login', json={'username':'admin','password':'admin@123456'})
token = resp.json()['access_token']
headers = {'Authorization': f'Bearer {token}'}

print('=== Data Summary ===')
resp = requests.get(f'{BASE_URL}/facilities/data-centers', headers=headers)
print(f'Data Centers: {resp.json().get("total", 0)}')

resp = requests.get(f'{BASE_URL}/facilities/rooms', headers=headers)
print(f'Rooms: {resp.json().get("total", 0)}')

resp = requests.get(f'{BASE_URL}/facilities/racks', headers=headers)
print(f'Racks: {resp.json().get("total", 0)}')

resp = requests.get(f'{BASE_URL}/devices/types/all', headers=headers)
print(f'Device Types: {len(resp.json())}')

resp = requests.get(f'{BASE_URL}/devices', headers=headers, params={'page': 1, 'page_size': 1})
print(f'Devices: {resp.json().get("total", 0)}')

resp = requests.get(f'{BASE_URL}/alerts', headers=headers)
print(f'Alerts: {resp.json().get("total", 0)}')

print('\\nPlease refresh the frontend to see the data!')
