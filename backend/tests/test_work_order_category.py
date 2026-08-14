# -*- coding: utf-8 -*-
"""Work order category (approval switch) update robustness tests."""

import itertools
from starlette.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def _auth(client) -> dict:
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Pytest-Admin-12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


_seq = itertools.count(1)

def _make_category(client, h):
    r = client.post("/api/v1/work-orders/categories",
                    json={"name": "Cat%d" % next(_seq), "code": "CAT%d" % next(_seq), "icon": "x", "sort": 1, "need_approval": False}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


def test_toggle_approval_persists():
    with TestClient(app) as client:
        h = _auth(client)
        cid = _make_category(client, h)
        on = client.put(f'/api/v1/work-orders/categories/{cid}', json={'need_approval': True}, headers=h)
        assert on.status_code == 200, on.text
        assert on.json()['data']['need_approval'] is True
        off = client.put(f'/api/v1/work-orders/categories/{cid}', json={'need_approval': False}, headers=h)
        assert off.status_code == 200, off.text
        assert off.json()['data']['need_approval'] is False


def test_empty_update_does_not_500():
    with TestClient(app) as client:
        h = _auth(client)
        cid = _make_category(client, h)
        r = client.put(f'/api/v1/work-orders/categories/{cid}', json={}, headers=h)
        assert r.status_code == 200, r.text

