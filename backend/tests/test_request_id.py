# -*- coding: utf-8 -*-
"""Request-ID ???????????

???
- ??? X-Request-ID ????? request-id ???????
- ???? X-Request-ID ???/??????
- contextvars ?? request-id ?? handler ???????????
- RequestIDFilter ?? request-id ???????
"""
import logging

from fastapi import FastAPI, Request
from starlette.testclient import TestClient

from app.core.request_id import (
    RequestIDMiddleware,
    RequestIDFilter,
    current_request_id,
)


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/x")
    async def handler(request: Request):
        return {"rid": current_request_id()}

    return app


class TestRequestIDMiddleware:
    def test_generates_request_id_when_absent(self):
        client = TestClient(_make_app())
        resp = client.get("/x")
        rid = resp.headers.get("x-request-id")
        assert rid and len(rid) >= 8
        assert resp.json()["rid"] == rid

    def test_echoes_incoming_request_id(self):
        client = TestClient(_make_app())
        resp = client.get("/x", headers={"X-Request-ID": "incoming-rid-123"})
        assert resp.headers.get("x-request-id") == "incoming-rid-123"
        assert resp.json()["rid"] == "incoming-rid-123" == "incoming-rid-123"


class TestRequestIDFilter:
    def test_filter_injects_req_id_and_defaults_to_dash(self):
        record = logging.LogRecord(
            name="t", level=logging.INFO, pathname=__file__,
            lineno=1, msg="msg", args=None, exc_info=None,
        )
        f = RequestIDFilter()
        # ?????? -> ?? "-"
        assert f.filter(record) is True
        assert record.req_id == "-"
        # ?????? -> ??
        import app.core.request_id as rid_mod
        token = rid_mod.request_id_var.set("ctx-abc")
        try:
            assert f.filter(record) is True
            assert record.req_id == "ctx-abc"
        finally:
            rid_mod.request_id_var.reset(token)


class TestRealAppRequestID:
    """???????/health ????? X-Request-ID?????????"""

    def test_real_app_health_has_request_id(self):
        from starlette.testclient import TestClient
        from app.main import app

        with TestClient(app) as client:
            resp = client.get("/health")
            assert resp.status_code == 200
            rid = resp.headers.get("x-request-id")
            assert rid and len(rid) >= 8

