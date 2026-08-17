# -*- coding: utf-8 -*-
"""
测试 /facilities/rooms/{room_id}/resources 资源统计接口：
机房下机柜按 U 位汇总 CPU 核数/内存/磁盘/GPU/算力/功率，并给出总计。
""".replace("“", "'").replace("”", "'")
from starlette.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def _login_ok(client) -> dict:
    r = client.post("/api/v1/auth/login",
                    json={"username": "admin", "password": "Pytest-Admin-12345"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_room_resources_aggregates_device_specs():
    with TestClient(app) as client:
        h = _login_ok(client)
        dc = client.post("/api/v1/facilities/data-centers",
                         json={"name": "RS-DC", "code": "RSDC", "status": "active"}, headers=h)
        assert dc.status_code == 201, dc.text
        room = client.post("/api/v1/facilities/rooms",
                           json={"data_center_id": dc.json()["id"], "name": "RS-Room",
                                 "code": "RS-RM", "floor": "1F"}, headers=h)
        assert room.status_code == 201, room.text
        rid = room.json()["id"]
        rack = client.post("/api/v1/facilities/racks",
                           json={"room_id": rid, "name": "RS-Rack", "code": "RS-RK-01",
                                 "total_units": 42, "available_units": 40, "status": "active",
                                 "rated_power": 5.0}, headers=h)
        assert rack.status_code == 201, rack.text
        # 创建设备类型
        dt = client.post("/api/v1/devices/types",
                         json={"name": "rs-server", "code": "rs-server", "category": "server", "status": "active"}, headers=h)
        assert dt.status_code == 201, dt.text
        # 在机柜上创建一台带结构化资源参数的设备
        dev = client.post("/api/v1/devices",
                          json={"name": "rs-srv-01", "asset_number": "RS-ASSET-01",
                                "device_type_id": dt.json()["id"],
                                "rack_id": rack.json()["id"], "start_u": 1, "end_u": 2,
                                "status": "mounted", "cpu_cores": 64,
                                "memory_gb": 256.0, "disk_capacity_gb": 4096.0,
                                "gpu_count": 4, "gpu_mem_gb": 80.0,
                                "compute_tflops": 300.0, "power_rating": 3.5,
                                "cpu_info": "AMD EPYC 7543"}, headers=h)
        assert dev.status_code == 201, dev.text
        r = client.get(f"/api/v1/facilities/rooms/{rid}/resources", headers=h)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["room"]["id"] == rid
        t = data["totals"]
        assert t["device_count"] == 1
        assert t["cpu_cores"] == 64
        assert abs(t["memory_gb"] - 256.0) < 0.5
        assert abs(t["disk_gb"] - 4096.0) < 0.5
        assert t["gpu_count"] == 4
        assert abs(t["gpu_mem_gb"] - 80.0) < 0.5
        assert abs(t["compute_tflops"] - 300.0) < 0.5
        assert abs(t["power_kw"] - 3.5) < 0.01
        assert t["rack_count"] == 1
        assert t["used_u"] == 2
        # 机柜小计
        assert len(data["racks"]) == 1
        rk = data["racks"][0]
        assert rk["cpu_cores"] == 64
        assert rk["used_u"] == 2
        # CPU 型号分布
        assert data["cpu_distribution"].get("AMD EPYC 7543") == 1
