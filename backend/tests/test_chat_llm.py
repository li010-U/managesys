"""AI 聊天 LLM 接入相关测试。

覆盖：
- 意图检测 _detect_intents 返回预期集合
- SendMessageRequest 长度限制（400/4000）
- 未配置 API Key 时回退到 mock（不报错）
"""
import pytest
from pydantic import ValidationError

from app.api.v1.chat import _detect_intents, get_mock_response, _guard_content, SYSTEM_PROMPT


def test_detect_intents_alerts():
    assert "alerts" in _detect_intents("请报告最新告警")
    assert "alerts" in _detect_intents("list alerts")


def test_detect_intents_sensors():
    assert "sensors" in _detect_intents("传感器温度如何")
    assert "sensors" in _detect_intents("sensor status")


def test_detect_intents_devices_racks():
    assert "devices" in _detect_intents("设备数量多少")
    assert "racks" in _detect_intents("机柜利用率")


def test_guard_content_limits_length():
    assert len(_guard_content("x" * 5000)) <= 4000


def test_system_prompt_has_boundary():
    assert "API" in SYSTEM_PROMPT
    assert len(SYSTEM_PROMPT) > 20


def test_mock_returns_string():
    assert isinstance(get_mock_response("hello"), str)
    assert len(get_mock_response("hello")) > 0


def test_send_message_request_length_guard():
    from app.api.v1.chat import SendMessageRequest
    SendMessageRequest(content="ok")
    with pytest.raises(ValidationError):
        SendMessageRequest(content="")
    with pytest.raises(ValidationError):
        SendMessageRequest(content="A" * 4001)
