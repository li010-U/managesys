"""AI chat tool-calling / confirmed-execution tests."""

import pytest

from app.services import ai_tools


def test_parse_proposal_create_work_order():
    user = "创建工单 标题: 服务器故障"
    answer = "已为您创建工单"
    p = ai_tools.parse_proposal(user, answer)
    assert p is not None
    assert p["tool"] == "create_work_order"
    assert p["args"]["title"] == "服务器故障"
    assert p["args"]["priority"] == "normal"


def test_parse_proposal_handle_alert():
    user = "请处理告警 #12 解决"
    p = ai_tools.parse_proposal(user, "")
    assert p is not None
    assert p["tool"] == "handle_alert"
    assert p["args"]["alert_id"] == 12
    assert p["args"]["action_type"] == "resolve"


def test_parse_proposal_non_actionable():
    assert ai_tools.parse_proposal("今天天气如何", "今天天气不错") is None
    assert ai_tools.parse_proposal("hello", "hi there") is None


def test_parse_proposal_alert_with_remark():
    user = "resolve alert 5, 备注: 器材已恢复"
    p = ai_tools.parse_proposal(user, "")
    assert p is not None
    assert p["tool"] == "handle_alert"
    assert p["args"]["alert_id"] == 5
    assert p["args"]["action_type"] == "resolve"
    assert p["args"]["remark"] == "器材已恢复"


def test_parse_proposal_plain_question_no_proposal():
    assert ai_tools.parse_proposal("设备数量多少", "") is None

@pytest.mark.asyncio
async def test_execute_create_work_order(db_session):
    from app.models import User
    user = User(username="tool_user", hashed_password="x", is_active=True)
    db_session.add(user)
    await db_session.flush()

    result = await ai_tools.execute(
        db_session,
        "create_work_order",
        {"title": "测试工单", "priority": "high"},
        "tool_user",
    )
    assert result["tool"] == "create_work_order"
    assert result["result"] == "created"
    assert result["order_no"]
    assert result["priority"] == "high"

    from sqlalchemy import select
    from app.models.work_order import WorkOrder
    rows = (await db_session.execute(select(WorkOrder))).scalars().all()
    assert any(w.title == "测试工单" for w in rows)


@pytest.mark.asyncio
async def test_execute_unknown_tool_raises(db_session):
    from app.models import User
    user = User(username="tool_user2", hashed_password="x", is_active=True)
    db_session.add(user)
    await db_session.flush()
    try:
        await ai_tools.execute(db_session, "nonexistent", {}, "tool_user2")
        assert False, "should raise"
    except ValueError:
        pass
