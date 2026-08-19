"""iputils 单元测试：客户端 IP 提取与 IP 分类。"""
from app.core.iputils import classify_ip, get_client_ip, location_label


def test_classify_private_ranges():
    assert classify_ip("10.1.2.3")["is_private"] is True
    assert classify_ip("192.168.0.1")["is_private"] is True
    assert classify_ip("172.16.5.5")["is_private"] is True
    assert classify_ip("100.64.0.1")["is_private"] is True


def test_classify_public_and_loopback():
    assert classify_ip("8.8.8.8")["is_public"] is True
    assert classify_ip("114.114.114.114")["is_public"] is True
    assert classify_ip("127.0.0.1")["category"] == "loopback"


def test_classify_invalid_and_ipv6():
    assert classify_ip("not-an-ip")["category"] == "invalid"
    assert classify_ip("240e:abcd::1")["is_ipv6"] is True
    assert classify_ip(None)["category"] == "unknown"


def test_location_label_helpers():
    assert "内网" in location_label("10.0.0.8")
    assert "公网" in location_label("1.1.1.1")
    assert location_label("") == "未知"


def test_get_client_ip_untrusted_default():
    """未配置可信代理（默认）时不信任转发头，直接返回直连 IP，杜绝伪造。"""
    assert get_client_ip("1.2.3.4, 10.0.0.1", "10.0.0.1", "10.0.0.1") == "10.0.0.1"
    # 即使伪造 X-Forwarded-For，仍取直连对端
    assert get_client_ip("6.6.6.6", None, "192.168.0.7") == "192.168.0.7"
    # X-Real-IP 同样不被信任
    assert get_client_ip(None, "5.6.7.8", "10.0.0.1") == "10.0.0.1"
    # 直连对端回退
    assert get_client_ip(None, None, "10.0.0.9") == "10.0.0.9"
    assert get_client_ip(None, None, None) == "unknown"


def test_get_client_ip_trusted_proxy(monkeypatch):
    """直连对端为可信代理时，才采用 X-Forwarded-For 最左（用户端）IP。"""
    import app.core.iputils as ipu
    monkeypatch.setattr(ipu, "TRUSTED_PROXIES", ["10.0.0.0/8"])
    # 直连在可信网段 -> 取转发头最左
    assert ipu.get_client_ip("1.2.3.4, 10.0.0.1", "10.0.0.1", "10.0.0.5") == "1.2.3.4"
    # 无 X-Forwarded-For 时回退 X-Real-IP
    assert ipu.get_client_ip(None, "5.6.7.8", "10.0.0.5") == "5.6.7.8"
    # 无转发头时回退直连对端
    assert ipu.get_client_ip(None, None, "10.0.0.5") == "10.0.0.5"


def test_get_client_ip_partial_trusted(monkeypatch):
    """直连对端不在可信网段时，即使代理头存在也不采用。"""
    import app.core.iputils as ipu
    monkeypatch.setattr(ipu, "TRUSTED_PROXIES", ["10.0.0.0/8"])
    assert ipu.get_client_ip("1.2.3.4", None, "192.168.5.9") == "192.168.5.9"


# IP 资源概览服务的纯逻辑函数
def test_clean_multi():
    from app.services.ip_resource_service import _clean_multi
    assert _clean_multi("10.0.0.1, 10.0.0.2") == ["10.0.0.1", "10.0.0.2"]
    assert _clean_multi("1.1.1.1;2.2.2.2") == ["1.1.1.1", "2.2.2.2"]
    assert _clean_multi(None) == []
    assert _clean_multi("  ") == []


def test_subnet24():
    from app.services.ip_resource_service import _subnet24
    assert _subnet24("192.168.1.5") == "192.168.1.0/24"
    assert _subnet24("bad") == "-"
