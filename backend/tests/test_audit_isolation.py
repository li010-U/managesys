# -*- coding: utf-8 -*-
"""审计所引失败隔离回归测试：审计写入任何异常都不得串到业务请求。
对应优化方案第①项“审计日志零信任重构”。
"""
import pytest
from app.services.audit_service import AuditService


class BadDB:
    """模拟 sqlite 被锁定 / 表被删除 / 会话异常的 db，add 就会抛错。"""
    def add(self, *a, **k):
        raise RuntimeError("simulated audit write failure")


def test_log_never_raises_and_returns_none_on_failure():
    r = AuditService.log(BadDB(), username="u", action="x", target_type="t")
    assert r is None


def test_log_request_never_raises_and_returns_none_on_failure():
    r = AuditService.log_request(BadDB(), request=None, current_user=None, action="x", target_type="t")
    assert r is None


def test_log_returns_audit_obj_on_normal_db(db_session):
    obj = AuditService.log(db_session, username="admin", action="test", target_type="unit", detail="hi")
    assert obj is not None
    assert obj.username == "admin"
    assert obj.action == "test"
