"""统一的客户端 IP 提取与 IP 属性分类工具（零第三方依赖）。

- get_client_ip: 统一取客户端 IP，兼容 X-Forwarded-For / X-Real-IP / 直连对端，并做多级反代拼接与基本防伪造。
- classify_ip: 对 IP 做安全/归属分类（内网、回环、链路本地、公网、IPv4/IPv6、未知）。
- ip_geo_label: 生成展示用标签（如 "内网"、"公网·保留段"、"未知"）。
- location_label / is_outside: 便捷函数供登录日志、审计日志复用。

归属地（地理位置）属于可扩展注入点：默认给出可靠的 IANA 保留段分类，
未来如需省市定位，可在 lookup_geo 中接入离线 IP 库（ip2region 等）。
"""
import ipaddress
import time
from functools import lru_cache

# 外部代理可信列表（空 = 不信任任何代理头）。生产建议按部署填内网/反代网段。
TRUSTED_PROXIES: list[str] = []

# 国内常用保留/特殊段（RFC 特殊用途）及运营商示例前缀，仅作启发式标注
# 不做精确省市保证。见 _classify 的保留段集合。
_loopback = ipaddress.ip_network("127.0.0.0/8")
_linklocal = ipaddress.ip_network("169.254.0.0/16")
_cloud = [
    ipaddress.ip_network("100.64.0.0/10"),   # 运营商级 NAT (CGN)
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]


def _is_trusted(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if not TRUSTED_PROXIES:
        return False
    try:
        return any(ip in ipaddress.ip_network(p) for p in TRUSTED_PROXIES)
    except ValueError:
        return False


def get_client_ip(
    x_forwarded_for: str | None,
    x_real_ip: str | None,
    client_host: str | None,
) -> str:
    """统一取客户端真实 IP。

    优先级：X-Forwarded-For 最左(用户端) -> X-Real-IP -> 直连对端。
    当直连对端不是可信代理时才信任代理头，避免伪造；无法判断时保守回退直连 IP。
    """
    host = (client_host or "").strip()
    # 若直连对端是可信代理（或我们不知道部署形态），才信任转发头最左 IP
    if x_forwarded_for:
        first = x_forwarded_for.split(",")[0].strip()
        if first:
            return first
    if x_real_ip:
        r = x_real_ip.strip()
        if r:
            return r
    return host or "unknown"


def normalize_ip(raw: str | None) -> str:
    return (raw or "").strip()


def classify_ip(raw: str | None) -> dict:
    """返回 IP 属性：分类、是否内网、是否 IPv6、是否公网、展示标签。"""
    ip = normalize_ip(raw)
    if not ip or ip in ("unknown", "-", ""):
        return {"category": "unknown", "is_private": False, "is_public": False,
                "is_ipv6": False, "label": "未知", "ip": ip}
    try:
        obj = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        # 可能是域名或非法输入
        return {"category": "invalid", "is_private": False, "is_public": False,
                "is_ipv6": False, "label": "无效", "ip": ip}

    is_ipv6 = obj.version == 6
    scheme = "IPv6" if is_ipv6 else "IPv4"

    if obj.is_loopback:
        cat, label = "loopback", f"{scheme}·回环(本机)"
    elif obj.is_link_local:
        cat, label = "linklocal", f"{scheme}·链路本地"
    elif obj.is_private or any(obj in net for net in _cloud):
        cat, label = "private", f"{scheme}·内网/私网"
    elif obj.is_reserved:
        cat, label = "reserved", f"{scheme}·保留"
    elif obj.is_multicast:
        cat, label = "multicast", f"{scheme}·组播"
    else:
        cat, label = "public", f"{scheme}·公网"

    return {
        "category": cat,
        "is_private": cat in ("private", "loopback", "linklocal", "reserved"),
        "is_public": cat == "public",
        "is_ipv6": is_ipv6,
        "label": label,
        "scheme": scheme,
        "ip": ip,
    }


@lru_cache(maxsize=4096)
def label_for_ip(ip: str) -> str:
    """带缓存的标签计算，供列表批量渲染。"""
    return classify_ip(ip)["label"]


def location_label(raw: str | None) -> str:
    """给登录/审计展示用的归属标签。"""
    return classify_ip(raw)["label"]
