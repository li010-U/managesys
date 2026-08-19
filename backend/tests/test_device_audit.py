# -*- coding: utf-8 -*-
"""设备/设备类型写操作审计留痕回归测试。

新增审计完善：devices.py 的所有写操作（device_type 增删改/阈值、
device 增删改/状态变更）应产生审计日志，与 users/roles/facilities 一致。
用真实 HTTP 栈走一遍写路径后，经 /audit-logs 校验留痕存在。
"""
from starlette.testclient import TestClient
from app.main import app


def _auth(client) -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"username": "admin", "password": "Pytest-Admin-12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _audit_for(client, h, target_type, action):
    """返回该 target_type+action 的审计条数。"""
    r = client.get(f"/api/v1/audit-logs?target_type={target_type}&action={action}&page_size=100",
                   headers=h)
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("items", body.get("data", []))
    return [it for it in items if it.get("target_type") == target_type and it.get("action") == action]


def test_device_write_operations_are_audited():
    with TestClient(app) as client:
        h = _auth(client)

        # 1) create device type -> audit create
        dt = client.post("/api/v1/devices/types",
                         json={"name": "Audit-Server", "code": "AUDSRV", "category": "server"}, headers=h)
        assert dt.status_code == 201, dt.text
        dt_id = dt.json()["id"]
        assert _audit_for(client, h, "device_type", "create"), "应产生 device_type create 审计"

        # 2) update device type -> audit update
        up = client.put(f"/api/v1/devices/types/{dt_id}",
                        json={"name": "Audit-Server-v2", "category": "server"}, headers=h)
        assert up.status_code == 200, up.text
        assert _audit_for(client, h, "device_type", "update"), "应产生 device_type update 审计"

        # 3) create device (needs rack) -> audit device create
        dc = client.post("/api/v1/facilities/data-centers",
                         json={"name": "AD-DC", "code": "ADDC", "status": "active"}, headers=h)
        assert dc.status_code == 201, dc.text
        room = client.post("/api/v1/facilities/rooms",
                           json={"data_center_id": dc.json()["id"], "name": "AD-Room",
                                 "code": "AD-RM-01", "floor": "1F"}, headers=h)
        assert room.status_code == 201, room.text
        rack = client.post("/api/v1/facilities/racks",
                           json={"room_id": room.json()["id"], "name": "Rack-A", "code": "RM-01-R",
                                 "total_units": 42, "available_units": 40, "rated_power": 10,
                                 "row_pos": 0, "col_pos": 0}, headers=h)
        assert rack.status_code == 201, rack.text

        dev = client.post("/api/v1/devices",
                          json={"device_type_id": dt_id, "rack_id": rack.json()["id"],
                                "name": "audit-srv-01", "asset_number": "AD-AST-001",
                                "status": "running", "power_rating": 2.0, "start_u": 1, "end_u": 2},
                          headers=h)
        assert dev.status_code == 201, dev.text
        dev_id = dev.json()["id"]
        assert _audit_for(client, h, "device", "create"), "应产生 device create 审计"

        # 4) update device -> audit device update
        ud = client.put(f"/api/v1/devices/{dev_id}",
                        json={"name": "audit-srv-01-updated"}, headers=h)
        assert ud.status_code == 200, ud.text
        assert _audit_for(client, h, "device", "update"), "应产生 device update 审计"

        # 5) change device status -> audit device change_status
        cs = client.put(f"/api/v1/devices/{dev_id}/status?status=offline", headers=h)
        assert cs.status_code == 200, cs.text
        assert _audit_for(client, h, "device", "change_status"), "应产生 device change_status 审计"

        # 6) delete device -> audit device delete
        dl = client.delete(f"/api/v1/devices/{dev_id}", headers=h)
        assert dl.status_code == 200, dl.text
        assert _audit_for(client, h, "device", "delete"), "应产生 device delete 审计"

        # 7) delete device type -> audit device_type delete
        dtd = client.delete(f"/api/v1/devices/types/{dt_id}", headers=h)
        assert dtd.status_code == 200, dtd.text
        assert _audit_for(client, h, "device_type", "delete"), "应产生 device_type delete 审计"


def test_facility_resource_update_is_audited():
    with TestClient(app) as client:
        h = _auth(client)
        dc = client.post("/api/v1/facilities/data-centers",
                         json={"name": "AD-DC2", "code": "ADDC2", "status": "active"}, headers=h)
        assert dc.status_code == 201, dc.text
        dc_id = dc.json()["id"]
        room = client.post("/api/v1/facilities/rooms",
                           json={"data_center_id": dc_id, "name": "AD-Room2", "code": "AD-RM-02", "floor": "2F"},
                           headers=h)
        assert room.status_code == 201, room.text
        room_id = room.json()["id"]
        rack = client.post("/api/v1/facilities/racks",
                           json={"room_id": room_id, "name": "Rack-B", "code": "RM-02-R",
                                 "total_units": 42, "available_units": 40, "rated_power": 10,
                                 "row_pos": 0, "col_pos": 0}, headers=h)
        assert rack.status_code == 201, rack.text
        rack_id = rack.json()["id"]

        # update each resource -> audit "update" for that target_type
        ud = client.put(f"/api/v1/facilities/data-centers/{dc_id}",
                        json={"name": "AD-DC2-r", "status": "active"}, headers=h)
        assert ud.status_code == 200, ud.text
        assert _audit_for(client, h, "data_center", "update"), "应产生 data_center update 审计"

        ur = client.put(f"/api/v1/facilities/rooms/{room_id}",
                        json={"name": "AD-Room2-r", "floor": "2F"}, headers=h)
        assert ur.status_code == 200, ur.text
        assert _audit_for(client, h, "room", "update"), "应产生 room update 审计"

        uk = client.put(f"/api/v1/facilities/racks/{rack_id}",
                        json={"name": "Rack-B-r", "available_units": 38}, headers=h)
        assert uk.status_code == 200, uk.text
        assert _audit_for(client, h, "rack", "update"), "应产生 rack update 审计"
