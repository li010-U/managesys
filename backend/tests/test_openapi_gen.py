# -*- coding: utf-8 -*-
"""\u3010\u7b2c\uff17\u9879\u3011\u4e3b\u94fe\u8def\u5192\u70df\uff1aOpenAPI \u6587\u6863\u751f\u6210\u5fc5\u987b\u6210\u529f\u3002
\u4fee\u590d\u524d\uff1a\u90e8\u5206\u7aef\u70b9\u7528\u4e86 request: Request \u4f46\u672a import Request\uff0c\u5bfc\u81f4
/ openapi.json \u8fd4\u56de 500\u3002\u6b64\u6d4b\u8bd5\u4fdd\u8bc1\u5168\u90e8\u7aef\u70b9\u7684\u6a21\u578b\u53ef\u6b63\u5e38\u751f\u6210\u65e0\u53ef\u89e3 ForwardRef\u3002
"""
from app.main import app


def test_openapi_schema_generates():
    schema = app.openapi()
    assert "paths" in schema
    assert schema["info"]["title"]
    assert len(schema["paths"]) > 50  # \u4e3b\u94fe\u8def\u7aef\u70b9\u4e0d\u53ef\u80fd\u592a\u5c11
