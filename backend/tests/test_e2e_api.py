# -*- coding: utf-8 -*-
"""E2E API regression test: walk the real HTTP stack end-to-end.

Covers the high-frequency regression areas called out in the audit:
- auth login through the real API
- create data-center -> room -> rack -> device-type -> device (real write path)
- 3D scene data contract via /rooms/{id}/rack3d (guards export source data)
- device IP -> IP-ledger auto-sync via /ip-registry/addresses (single source of truth)

Uses an isolated temporary SQLite so it never touches the live database.
"""
from starlette.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def _auth(client) -> dict:
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "Pytest-Admin-12345"},
    )
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_e2e_3d_scene_and_ip_ledger_flow():
    with TestClient(app) as client:
        h = _auth(client)

        # 1) create data-center
        dc = client.post("/api/v1/facilities/data-centers",
                         json={"name": "E2E-DC", "code": "E2EDC", "status": "active"}, headers=h)
        assert dc.status_code == 201, dc.text
        dc_id = dc.json()["id"]

        # 2) create room
        room = client.post("/api/v1/facilities/rooms",
                           json={"data_center_id": dc_id, "name": "E2E-Room", "code": "E2E-RM-01", "floor": "3F"},
                           headers=h)
        assert room.status_code == 201, room.text
        room_id = room.json()["id"]

        # 3) create rack
        rack = client.post("/api/v1/facilities/racks",
                           json={"room_id": room_id, "name": "Rack-01", "code": "E2E-RM-01-01",
                                 "total_units": 42, "available_units": 40, "rated_power": 10,
                                 "row_pos": 0, "col_pos": 0}, headers=h)
        assert rack.status_code == 201, rack.text
        rack_id = rack.json()["id"]

        # 4) create device type
        dt = client.post("/api/v1/devices/types",
                         json={"name": "E2E-Server", "code": "E2ESRV", "category": "server"}, headers=h)
        assert dt.status_code == 201, dt.text
        dt_id = dt.json()["id"]

        # 5) create IP subnet (for ledger membership)
        sub = client.post("/api/v1/ip-registry/subnets",
                          json={"name": "E2E-Subnet", "network": "10.200.0.0", "prefix": 22}, headers=h)
        assert sub.status_code == 201, sub.text

        # 6) create device with IPs -> ledger auto-sync
        dev = client.post("/api/v1/devices",
                          json={"device_type_id": dt_id, "rack_id": rack_id, "name": "srv-e2e-01",
                                "asset_number": "E2E-AST-001", "status": "running",
                                "power_rating": 2.5, "start_u": 5, "end_u": 8,
                                "management_ip": "10.200.0.10", "business_ip": "10.200.0.11"}, headers=h)
        assert dev.status_code == 201, dev.text

        # 7) 3D scene contract reflects the device at correct U-position + power
        scene = client.get(f"/api/v1/facilities/rooms/{room_id}/rack3d", headers=h)
        assert scene.status_code == 200, scene.text
        body = scene.json()
        racks = body.get("racks", [])
        assert len(racks) >= 1
        r = next(x for x in racks if x["code"] == "E2E-RM-01-01")
        devs = {d["name"]: d for d in r.get("devices", [])}
        assert "srv-e2e-01" in devs
        assert devs["srv-e2e-01"]["start_u"] == 5
        assert devs["srv-e2e-01"]["end_u"] == 8
        # power_load = 2.5 (only running device counted)
        assert r.get("power_load", 0) == 2.5

        # 8) IP ledger synced the device IPs (single source of truth)
        ledger = client.get("/api/v1/ip-registry/addresses?page_size=100", headers=h)
        assert ledger.status_code == 200, ledger.text
        items = ledger.json().get("items", ledger.json().get("data", []))
        addrs = {it["address"]: it for it in items}
        assert "10.200.0.10" in addrs and addrs["10.200.0.10"]["status"] == "allocated"
        assert "10.200.0.11" in addrs and addrs["10.200.0.11"]["status"] == "allocated"
