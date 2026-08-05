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
def test_detect_repetition_snowball():
    from app.api.v1.chat import _detect_repetition, _trim_repetition
    base = "\u6839\u636e\u5f53\u524d\u7cfb\u7edf\u6570\u636e\uff0c\u4eca\u65e5\u8fd0\u7ef4\u5efa\u8bae\u5982\u4e0b\uff1a1. \u544a\u8b66\u5904\u7406\uff1a\u5f53\u524d\u5f85\u5904\u7406\u544a\u8b66\u4e3a0\uff0c\u5df2\u786e\u8ba420\u6761\uff0c\u5efa\u8bae\u5c3d\u5feb\u6838\u5b9e"
    roll = base * 30
    assert _detect_repetition(roll) is True
    trimmed = _trim_repetition(roll)
    assert len(trimmed) < len(roll)
    assert _detect_repetition(trimmed) is False


def test_detect_repetition_normal_text():
    from app.api.v1.chat import _detect_repetition, _trim_repetition
    normal = "\u4eca\u65e5\u8fd0\u7ef4\u5efa\u8bae\u5982\u4e0b\uff1a\u4f20\u611f\u5668\u72b6\u6001\u826f\u597d\uff0c\u5171\u670968\u4e2a\u4f20\u611f\u5668\u5728\u7ebf\uff0c\u8fd0\u884c\u5e73\u7a33\u3002"
    assert _detect_repetition(normal) is False
    assert _trim_repetition(normal) == normal
