import urllib.request, json, sys

data = json.dumps({"username": "admin", "password": "admin@123456"}).encode()
req = urllib.request.Request("http://127.0.0.1:8000/api/v1/auth/login", data=data, headers={"Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(req)
    token = json.loads(resp.read())["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    ok = 0
    for ep in ["/api/v1/facilities/data-centers?page=1&page_size=10", "/api/v1/facilities/rooms?page=1&page_size=10", "/api/v1/facilities/racks?page=1&page_size=10", "/api/v1/devices/types?page=1&page_size=10", "/api/v1/devices?page=1&page_size=10"]:
        req = urllib.request.Request(f"http://127.0.0.1:8000{ep}", headers=headers)
        urllib.request.urlopen(req)
        ok += 1
        print(f"  {ep[18:-18]}... -> OK")
    print(f"\n{ok}/{ok} API endpoints working!")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)