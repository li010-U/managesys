"""IP 资源概览服务：基于设备台账的 IP 字段实时聚合。

不引入新表；以设备管理/业务/带外 IP 为数据源，
输出：IP 类型计数、网段分组、以及 IP 冲突检测（同字段重复为明确冲突，
跨字段重复为潜在冲突）。
"""
import ipaddress
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device


def _null(v) -> bool:
    return v is None or str(v).strip() == ""


def _clean_multi(raw) -> list[str]:
    """业务 IP 可能用逗号/分号/空格分隔多个地址。"""
    if _null(raw):
        return []
    out = []
    for part in str(raw).replace(";", ",").replace("，", ",").split(","):
        p = part.strip()
        if p:
            out.append(p)
    return out


def _subnet24(ip_str: str) -> str:
    try:
        ip = ipaddress.ip_address(ip_str.split("%")[0])
        if ip.version == 4:
            return f"{str(ip)[: str(ip).rfind('.')]}.0/24"
        return f"{ip.exploded[:19]}::/64"
    except ValueError:
        return "-"


class IpResourceService:
    """IP 资源概览服务。"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def overview(self) -> dict:
        result = await self.db.execute(
            select(
                Device.id, Device.name, Device.asset_number,
                Device.management_ip, Device.business_ip, Device.out_of_band_ip,
                Device.rack_id, Device.status,
            )
        )
        rows = result.all()

        # 类型计数（按去重后的 IP 计算）
        role_counts = defaultdict(int)
        # 收集：role -> ip -> [(device)]
        by_role: dict[str, dict[str, list[dict]]] = {}
        # 全局 ip -> roles（跨字段）
        global_ip: dict[str, set[str]] = defaultdict(set)
        all_ips: list[dict] = []

        for r in rows:
            device = {"id": r.id, "name": r.name, "asset_number": r.asset_number,
                      "status": r.status, "rack_id": r.rack_id}
            roles = {
                "management": _clean_multi(r.management_ip),
                "business": _clean_multi(r.business_ip),
                "oob": _clean_multi(r.out_of_band_ip),
            }
            for role, iplist in roles.items():
                for ip in iplist:
                    by_role.setdefault(role, {}).setdefault(ip, []).append({**device, "role": role})
                    global_ip[ip].add(role)
                    all_ips.append({**device, "role": role, "ip": ip})
                    role_counts[role] += 1

        # 明确冲突：同一 role 同一 ip 出现于多个设备
        conflicts = []
        for role, mapping in by_role.items():
            for ip, devices in mapping.items():
                if len(devices) > 1:
                    conflicts.append({"ip": ip, "role": role, "devices": devices})
        # 潜在冲突：同一 ip 出现在不同 role（不同网卡可能合法，仅提示）
        potential = []
        for ip, roles in global_ip.items():
            if len(roles) > 1:
                potential.append({"ip": ip, "roles": sorted(roles)})

        # 网段分组（用管理 IP 为主，业务/带外也计入）
        subnets: dict[str, dict] = {}
        for it in all_ips:
            s = _subnet24(it["ip"])
            bucket = subnets.setdefault(s, {"subnet": s, "total": 0, "public": 0, "private": 0, "ips": []})
            bucket["total"] += 1
            try:
                ip = ipaddress.ip_address(it["ip"].split("%")[0])
                if ip.version == 4 and (ip.is_private or ip.is_loopback or ip.is_link_local):
                    bucket["private"] += 1
                elif ip.version == 4:
                    bucket["public"] += 1
            except ValueError:
                pass
            bucket["ips"].append(it)

        uniq_ips = set(it["ip"] for it in all_ips)
        return {
            "total_entries": len(all_ips),
            "unique_ips": len(uniq_ips),
            "device_count": len(rows),
            "role_counts": dict(role_counts),
            "role_labels": {
                "management": "管理IP",
                "business": "业务IP",
                "oob": "带外IP",
            },
            "conflicts": sorted(conflicts, key=lambda x: (x["role"], x["ip"])),
            "potential_conflicts": sorted(potential, key=lambda x: x["ip"]),
            "conflict_count": len(conflicts),
            "subnets": sorted(subnets.values(), key=lambda x: x["subnet"]),
        }
