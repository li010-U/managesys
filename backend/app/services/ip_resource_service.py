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

    def _collect(self, rows):
        """???? IP ???????? overview/conflicts ???"""
        from collections import defaultdict
        by_role = defaultdict(lambda: defaultdict(list))  # role -> ip -> [device]
        global_ip = defaultdict(set)                      # ip -> roles
        all_ips = []
        for r in rows:
            device = {
                "id": r.id, "name": r.name, "asset_number": r.asset_number,
                "status": r.status, "rack_id": r.rack_id,
            }
            roles = {
                "management": _clean_multi(r.management_ip),
                "business": _clean_multi(r.business_ip),
                "oob": _clean_multi(r.out_of_band_ip),
            }
            for role, iplist in roles.items():
                for ip in iplist:
                    by_role[role][ip].append({**device, "role": role})
                    global_ip[ip].add(role)
                    all_ips.append({**device, "role": role, "ip": ip})
        return by_role, global_ip, all_ips


    async def _rack_room_map(self) -> dict:
        """?? {rack_id: (rack_name, room_id)} ??????????"""
        from app.models.facility import Rack
        out = {}
        try:
            res = await self.db.execute(select(Rack.id, Rack.name, Rack.room_id))
            for rid, rname, room_id in res.all():
                out[rid] = (rname, room_id)
        except Exception:
            out = {}
        return out

    async def conflicts(self) -> dict:
        """??????????????? + ??????????????"""
        result = await self.db.execute(
            select(
                Device.id, Device.name, Device.asset_number,
                Device.management_ip, Device.business_ip, Device.out_of_band_ip,
                Device.rack_id, Device.status,
            )
        )
        rows = result.all()
        room_map = await self._rack_room_map()
        by_role, global_ip, _ = self._collect(rows)

        def _enrich(devices):
            for d in devices:
                rid = d.get("rack_id")
                if rid in room_map:
                    d["rack_name"] = room_map[rid][0]
                    d["room_id"] = room_map[rid][1]
                    d["racked"] = True
                else:
                    d["rack_name"] = "未挂载"
                    d["room_id"] = None
                    d["racked"] = False
            return devices

        explicit = []
        for role, mapping in by_role.items():
            for ip, devices in mapping.items():
                if len(devices) > 1:
                    explicit.append({
                        "ip": ip, "role": role, "devices": _enrich(devices),
                        "conflict_type": "explicit",
                    })
        explicit.sort(key=lambda x: (x["role"], x["ip"]))

        potential = []
        for ip, roles in global_ip.items():
            if len(roles) > 1:
                potential.append({
                    "ip": ip, "roles": sorted(roles),
                    "devices": _enrich(self._devices_for_ip(rows, ip)),
                    "conflict_type": "potential",
                })
        potential.sort(key=lambda x: x["ip"])

        return {
            "explicit": explicit,
            "potential": potential,
            "total": len(explicit) + len(potential),
        }

    @staticmethod
    def _devices_for_ip(rows, ip: str) -> list:
        out = []
        for r in rows:
            roles = {"management": _clean_multi(r.management_ip),
                     "business": _clean_multi(r.business_ip),
                     "oob": _clean_multi(r.out_of_band_ip)}
            for role, iplist in roles.items():
                if ip in iplist:
                    out.append({
                        "id": r.id, "name": r.name, "asset_number": r.asset_number,
                        "status": r.status, "rack_id": r.rack_id, "role": role,
                        "racked": False, "rack_name": "未挂载",
                    })
        return out

    async def resolve_conflict(self, device_id: int, role: str, new_ip: str,
                               operator_username: str = None, operator_ip: str = None) -> dict:
        """??????????? role ???? IP?????????????

        ???{"device": {...}, "ip": new_ip, "role": role, "remaining_conflicts": int}
        """
        from app.models.device import Device
        from app.services.audit_service import AuditService

        role_field = {"management": "management_ip",
                      "business": "business_ip",
                      "oob": "out_of_band_ip"}.get(role)
        if role_field is None:
            raise ValueError("??? IP ????")
        new_ip = (new_ip or "").strip()
        if not new_ip:
            raise ValueError("? IP ????")

        # ??? IP ???????
        try:
            ipaddress.ip_address(new_ip.split("%")[0])
        except ValueError:
            raise ValueError("? IP ?????")

        device = (await self.db.execute(
            select(Device).where(Device.id == device_id)
        )).scalar_one_or_none()
        if device is None:
            raise ValueError("?????")

        old_value = getattr(device, role_field) or ""
        setattr(device, role_field, new_ip)
        await self.db.commit()

        # ??? IP ??????????? conflicts???????????
        remaining = await self._count_conflicts_after(device_id, role, new_ip)

        AuditService.log(
            self.db,
            username=operator_username or "system",
            action="ip_conflict_resolve",
            target_type="device",
            user_id=None,
            target_id=str(device_id),
            detail=("?? IP ???%s[%s] ??=%s?IP %s -> %s"
                    % (device.name, device.asset_number, role, old_value, new_ip)),
            ip_address=operator_ip,
        )
        await self.db.commit()

        return {
            "device": {"id": device.id, "name": device.name, "asset_number": device.asset_number,
                       "new_ip": new_ip, "role": role},
            "old_ip": old_value,
            "new_ip": new_ip,
            "remaining_conflicts": remaining,
        }

    async def _count_conflicts_after(self, device_id: int, role: str, new_ip: str) -> int:
        """????????????????????????????"""
        result = await self.db.execute(
            select(
                Device.id, Device.name, Device.asset_number,
                Device.management_ip, Device.business_ip, Device.out_of_band_ip,
                Device.rack_id, Device.status,
            )
        )
        rows = result.all()
        by_role, _, _ = self._collect(rows)
        count = 0
        for r, mapping in by_role.items():
            for ip, devices in mapping.items():
                if len(devices) > 1:
                    count += 1
        return count
