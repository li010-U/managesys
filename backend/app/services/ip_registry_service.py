"""IP 地址台账与子网管理服务。

在原有“基于设备字段实时聚合”之上，增加：
- 子网定义管理（网段/掩码/网关/VLAN）；
- IP 台账条目（分配/预留/空闲状态、归属设备）；
- 子网使用率与剩余容量统计；
- 从设备字段自动导入 IP 到台账。
"""
import ipaddress
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ip_address import IpSubnet, IpAddress, IpAddressHistory
from app.models.device import Device
from app.models.vlan import Vlan
from app.models.facility import Room


IP_STATUS = {"free", "reserved", "allocated"}


def write_ip_history(db, ip_id, address, field_changed, from_value, to_value,
                     operator=None, source="manual", remark=None):
    """写一条 IP 台账变更历史，供回放与审计追溯。"""
    db.add(IpAddressHistory(ip_id=ip_id, address=address, field_changed=field_changed,
                            from_value=from_value, to_value=to_value, operator=operator,
                            source=source, remark=remark))


async def validate_no_conflict(db, ip_str, role=None, exclude_address=None, exclude_device_id=None, raise_on_conflict=True):
    """\u5206\u914d\u524d\u9632\u51b2\u7a81\u6821\u9a8c\uff1a\u4e0b\u7ebf\u67e5\u627e\u662f\u5426\u5df2\u6709\u5176\u4ed6\u8bbe\u5907\u5360\u7528\u8be5 IP\u3002
    \u4e0d\u533a\u5206\u89d2\u8272\u7684\u300e\u540c\u4e00 IP \u4e0d\u5f97\u88ab\u4e24\u53f0\u4e0d\u540c\u8bbe\u5907\u540c\u65f6\u5360\u7528\u300f\u4e3a\u786e\u5b9a\u51b2\u7a81\u5236\u7ea6\u3002
    \u8fd4\u56de\u51b2\u7a81\u8bbe\u5907\uff1b\u82e5 raise_on_conflict \u4e3a\u771f\u4e14\u53d1\u751f\u51b2\u7a81\u5219\u629b\u51fa ValueError\u3002"""
    if not ip_str:
        return None
    addr = ip_str.strip()
    row = (await db.execute(select(IpAddress).options(selectinload(IpAddress.device)).where(IpAddress.address == addr))).scalar_one_or_none()
    if row is None:
        return None
    if exclude_address is not None and row.address == exclude_address:
        return None
    if exclude_device_id is not None and row.device_id == exclude_device_id and row.status == "allocated":
        return None
    if row.status != "allocated":
        return None
    if raise_on_conflict:
        holder = row.device.name if row.device else (str(row.device_id) if row.device_id else None)
        raise ValueError(addr + " \u5df2\u88ab\u8bbe\u5907 " + (holder or "\u672a\u77e5") + " \u5360\u7528\uff0c\u8bf7\u91cd\u65b0\u9009\u62e9")
    return row


def _capacity(ip: IpSubnet) -> int:
    """按 CIDR 计算子网地址容量（IPv4: 2^(32-prefix)，IPv6: 2^(128-prefix)）。"""
    try:
        net = ipaddress.ip_network(f"{ip.network}/{ip.prefix}", strict=False)
    except (ValueError, TypeError):
        return 0
    if net.version == 4:
        return 1 << (32 - ip.prefix)
    # IPv6 容量极大，返回 2^64 封顶用于展示
    return (1 << 64) - 1 if ip.prefix <= 64 else (1 << (128 - ip.prefix))


class IpRegistryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_subnets(self) -> list[dict]:
        """\u7f51\u6bb5\u6e05\u5355\uff0c\u542b VLAN / \u673a\u623f\u5173\u8054\u4e0e\u4f7f\u7528\u7387\u6c34\u4f4d\u6807\u8bb0\u3002"""
        result = await self.db.execute(select(IpSubnet).order_by(IpSubnet.network, IpSubnet.prefix))
        subnets = result.scalars().all()
        used_rows = (await self.db.execute(
            select(IpAddress.subnet_id, IpAddress.status, func.count(IpAddress.id).label("cnt"))
            .where(IpAddress.subnet_id.isnot(None))
            .group_by(IpAddress.subnet_id, IpAddress.status)
        )).all()
        used = {}
        for subnet_id, status, cnt in used_rows:
            used.setdefault(subnet_id, {"allocated": 0, "reserved": 0, "free": 0})
            if status in used[subnet_id]:
                used[subnet_id][status] += cnt

        vlan_ids = [s.vlan_id for s in subnets if s.vlan_id]
        vlan_map = {}
        room_map = {}
        if vlan_ids:
            for v in (await self.db.execute(select(Vlan).where(Vlan.id.in_(vlan_ids)))).scalars().all():
                vlan_map[v.id] = v
            rids = [v.room_id for v in vlan_map.values() if v.room_id]
            if rids:
                for rm in (await self.db.execute(select(Room).where(Room.id.in_(rids)))).scalars().all():
                    room_map[rm.id] = rm

        out = []
        for sub in subnets:
            capacity = _capacity(sub)
            alloc = used.get(sub.id, {}).get("allocated", 0)
            resv = used.get(sub.id, {}).get("reserved", 0)
            free = max(capacity - alloc - resv, 0) if capacity else 0
            usage = (alloc + resv) / capacity * 100 if capacity else 0
            vobj = vlan_map.get(sub.vlan_id) if sub.vlan_id else None
            room = room_map.get(vobj.room_id) if vobj and vobj.room_id else None
            out.append({
                "id": sub.id,
                "name": sub.name,
                "network": sub.network,
                "prefix": sub.prefix,
                "cidr": f"{sub.network}/{sub.prefix}",
                "gateway": sub.gateway,
                "vlan": sub.vlan,
                "vlan_id": sub.vlan_id,
                "vlan_name": (vobj.name or ("VLAN " + str(vobj.vlan_id))) if vobj else None,
                "room_id": room.id if room else None,
                "room_name": room.name if room else None,
                "description": sub.description,
                "status": sub.status,
                "capacity": capacity,
                "allocated": alloc,
                "reserved": resv,
                "free": free,
                "usage": round(usage, 2),
                "over_watermark": usage >= 80,
                "watermark": 80,
            })
        return out

    async def list_vlans(self) -> list[dict]:
        """\u0056LAN \u6e05\u5355\uff0c\u5404 VLAN \u9601\u4e0b\u5b50\u7f51\u6570\u4e0e\u603b\u4f7f\u7528\u7387\u3002"""
        vlans = (await self.db.execute(select(Vlan).order_by(Vlan.vlan_id))).scalars().all()
        subnets = (await self.db.execute(select(IpSubnet))).scalars().all()
        addr_rows = (await self.db.execute(
            select(IpAddress.subnet_id, IpAddress.status, func.count(IpAddress.id).label("cnt"))
            .where(IpAddress.subnet_id.isnot(None))
            .group_by(IpAddress.subnet_id, IpAddress.status)
        )).all()
        sub_usage = {}
        for sid, status, cnt in addr_rows:
            sub_usage.setdefault(sid, {"allocated": 0, "reserved": 0})
            if status in sub_usage[sid]:
                sub_usage[sid][status] += cnt
        room_ids = {v.room_id for v in vlans if v.room_id}
        rooms = {}
        if room_ids:
            for rm in (await self.db.execute(select(Room).where(Room.id.in_(room_ids)))).scalars().all():
                rooms[rm.id] = rm
        out = []
        for v in vlans:
            vsubs = [s for s in subnets if s.vlan_id == v.id]
            cap = sum(_capacity(s) for s in vsubs)
            alloc = sum(sub_usage.get(s.id, {}).get("allocated", 0) for s in vsubs)
            resv = sum(sub_usage.get(s.id, {}).get("reserved", 0) for s in vsubs)
            usage = (alloc + resv) / cap * 100 if cap else 0
            rm = rooms.get(v.room_id) if v.room_id else None
            out.append({
                "id": v.id, "vlan_id": v.vlan_id, "name": v.name,
                "description": v.description, "status": v.status,
                "room_id": v.room_id, "room_name": rm.name if rm else None,
                "subnet_count": len(vsubs), "capacity": cap,
                "allocated": alloc, "reserved": resv, "usage": round(usage, 2),
                "over_watermark": usage >= 80, "watermark": 80,
            })
        return out

    async def create_vlan(self, vlan_id: int, name: str = "", description: Optional[str] = None,
                          room_id: Optional[int] = None, status: str = "active") -> Vlan:
        if (await self.db.execute(select(Vlan).where(Vlan.vlan_id == vlan_id))).scalar_one_or_none():
            raise ValueError("\u8be5 VLAN \u7f16\u53f7\u5df2\u5b58\u5728")
        v = Vlan(vlan_id=vlan_id, name=name, description=description, room_id=room_id, status=status)
        self.db.add(v)
        await self.db.flush()
        await self.db.refresh(v)
        return v

    async def update_vlan(self, vlan_pk: int, name=None, description=..., room_id=..., status=None) -> Optional[Vlan]:
        v = (await self.db.execute(select(Vlan).where(Vlan.id == vlan_pk))).scalar_one_or_none()
        if not v:
            return None
        if name is not None:
            v.name = name
        if description is not ...:
            v.description = description
        if room_id is not ...:
            v.room_id = room_id
        if status is not None:
            v.status = status
        await self.db.flush()
        await self.db.refresh(v)
        return v

    async def delete_vlan(self, vlan_pk: int) -> bool:
        v = (await self.db.execute(select(Vlan).where(Vlan.id == vlan_pk))).scalar_one_or_none()
        if not v:
            return False
        # \u5c06\u5176\u4e0b\u5b50\u7f51\u7684 vlan_id \u6e05\u7a7a\uff0c\u907f\u514d\u60ac\u7a7a\u5f15\u7528
        for s in (await self.db.execute(select(IpSubnet).where(IpSubnet.vlan_id == vlan_pk))).scalars().all():
            s.vlan_id = None
        await self.db.delete(v)
        await self.db.flush()
        return True

    async def export_subnets_csv(self) -> str:
        """\u5bfc\u51fa\u7f51\u6bb5\u53f0\u8d26 CSV\u3002"""
        import csv, io
        subs = await self.list_subnets()
        buf = io.StringIO()
        buf.write("\ufeff")
        w = csv.writer(buf)
        w.writerow(["\u540d\u79f0", "CIDR", "\u7f51\u5173", "VLAN", "\u673a\u623f",
                    "\u603b\u5bb9\u91cf", "\u5df2\u5206\u914d", "\u9884\u7559", "\u7a7a\u95f2",
                    "\u4f7f\u7528\u7387(%)", "\u72b6\u6001"])
        for s in subs:
            w.writerow([s["name"], s["cidr"], s["gateway"] or "", s["vlan_name"] or s["vlan"] or "",
                        s["room_name"] or "", s["capacity"], s["allocated"], s["reserved"], s["free"],
                        s["usage"], s["status"]])
        return buf.getvalue()

    async def export_addresses_csv(self, subnet_id: Optional[int] = None, status: Optional[str] = None) -> str:
        """\u5bfc\u51fa IP \u53f0\u8d26 CSV\u3002"""
        import csv, io
        items, _ = await self.list_addresses(subnet_id, status, None, 1, 100000)
        buf = io.StringIO()
        buf.write("\ufeff")
        w = csv.writer(buf)
        w.writerow(["IP\u5730\u5740", "\u72b6\u6001", "\u6240\u5c5e\u7f51\u6bb5", "\u5360\u7528\u8bbe\u5907",
                    "\u7528\u9014", "\u5907\u6ce8", "\u66f4\u65b0\u65f6\u95f4"])
        for it in items:
            w.writerow([it["address"], it["status"], it["subnet"] or "", it["device_name"] or "",
                        it["used_as"] or "", it["remark"] or "",
                        (it["updated_at"].strftime("%Y-%m-%d %H:%M") if it["updated_at"] else "")])
        return buf.getvalue()

    async def create_subnet(self, name, network, prefix, gateway=None, vlan=None, vlan_id=None, description=None, status="active") -> IpSubnet:
        # 校验 CIDR
        try:
            net = ipaddress.ip_network(f"{network}/{prefix}", strict=False)
            network = str(net.network_address)
        except ValueError as e:
            raise ValueError(f"网段格式不正确: {e}")
        exists = (await self.db.execute(select(IpSubnet).where(IpSubnet.network == network, IpSubnet.prefix == prefix))).scalar_one_or_none()
        if exists:
            raise ValueError("该网段已存在")
        sub = IpSubnet(name=name, network=network, prefix=prefix, gateway=gateway, vlan=vlan, vlan_id=vlan_id, description=description, status=status)
        self.db.add(sub)
        await self.db.flush()
        await self.db.refresh(sub)
        return sub

    async def update_subnet(self, subnet_id: int, name=None, gateway=None, vlan=None, vlan_id=None, description=None, status=None) -> Optional[IpSubnet]:
        sub = (await self.db.execute(select(IpSubnet).where(IpSubnet.id == subnet_id))).scalar_one_or_none()
        if not sub:
            return None
        if name is not None: sub.name = name
        if gateway is not None: sub.gateway = gateway
        if vlan is not None: sub.vlan = vlan
        if vlan_id is not None: sub.vlan_id = vlan_id
        if description is not None: sub.description = description
        if status is not None: sub.status = status
        await self.db.flush()
        await self.db.refresh(sub)
        return sub

    async def delete_subnet(self, subnet_id: int) -> bool:
        sub = (await self.db.execute(select(IpSubnet).where(IpSubnet.id == subnet_id))).scalar_one_or_none()
        if not sub:
            return False
        cnt = (await self.db.execute(
            select(func.count()).select_from(IpAddress).where(IpAddress.subnet_id == subnet_id)
        )).scalar() or 0
        if cnt:
            raise HTTPException(status_code=409, detail=f"该子网下仍有 {cnt} 个 IP 地址，请先清除后再删除")
        await self.db.delete(sub)
        await self.db.flush()
        return True

    async def list_addresses(self, subnet_id: Optional[int] = None, status: Optional[str] = None, keyword: Optional[str] = None, page: int = 1, page_size: int = 20):
        conditions = []
        if subnet_id is not None:
            conditions.append(IpAddress.subnet_id == subnet_id)
        if status:
            conditions.append(IpAddress.status == status)
        if keyword:
            conditions.append(or_(IpAddress.address.ilike(f'%{keyword}%'), IpAddress.remark.ilike(f'%{keyword}%')))

        base = select(IpAddress).options(
            selectinload(IpAddress.subnet),
            selectinload(IpAddress.device),
        ).where(*conditions) if conditions else select(IpAddress).options(
            selectinload(IpAddress.subnet),
            selectinload(IpAddress.device),
        )
        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
        rows = (await self.db.execute(
            base.order_by(IpAddress.address).offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()

        items = []
        for r in rows:
            items.append({
                'id': r.id,
                'address': r.address,
                'status': r.status,
                'subnet_id': r.subnet_id,
                'subnet': f'{r.subnet.network}/{r.subnet.prefix}' if r.subnet else None,
                'device_id': r.device_id,
                'device_name': r.device.name if r.device else None,
                'used_as': r.used_as,
                'remark': r.remark,
                'updated_at': r.updated_at,
            })
        return items, total

    async def allocate_ip(self, subnet_id: int, role: str = "management", device_id: Optional[int] = None,
                           operator: Optional[str] = None, source: str = "allocate",
                           preferred: Optional[str] = None) -> dict:
        """从指定子网自动分配一个空闲 IP（跳过网络/广播地址与网关）。
        分配前行 IP 取消已用地址与其他设备占用检查。"""
        sub = (await self.db.execute(select(IpSubnet).where(IpSubnet.id == subnet_id))).scalar_one_or_none()
        if not sub:
            raise ValueError("子网不存在")
        try:
            net = ipaddress.ip_network(f"{sub.network}/{sub.prefix}", strict=False)
        except (ValueError, TypeError):
            raise ValueError("子网格式无效")

        used = set()
        for row in (await self.db.execute(select(IpAddress.address).where(IpAddress.subnet_id == subnet_id))).scalars().all():
            try:
                used.add(int(ipaddress.ip_address(row.split("%")[0])))
            except ValueError:
                continue

        skip = set()
        if net.version == 4:
            skip.add(int(net.network_address))
            skip.add(int(net.network_address) + int(net.num_addresses) - 1)
            if sub.gateway:
                try:
                    skip.add(int(ipaddress.ip_address(sub.gateway)))
                except ValueError:
                    pass

        candidates = [int(a) for a in net.hosts()] if net.version == 4 else []
        if preferred:
            try:
                p = int(ipaddress.ip_address(preferred.split("%")[0]))
                if p in candidates and p not in used and p not in skip:
                    candidates.insert(0, p)
            except ValueError:
                pass

        chosen = None
        for a in candidates:
            if a in used or a in skip:
                continue
            chosen = ipaddress.ip_address(a)
            break
        if chosen is None:
            raise ValueError("该子网已无可用空闲地址")

        addr = str(chosen)
        # 确保不与他设备冲突
        await validate_no_conflict(self.db, addr, role=role, exclude_device_id=device_id if device_id else None)
        row = IpAddress(address=addr, status="allocated", subnet_id=subnet_id, device_id=device_id,
                        used_as=role, remark=None)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        write_ip_history(self.db, row.id, addr, "device", None, str(device_id) if device_id else None,
                         operator=operator, source=source)
        return {"id": row.id, "address": addr, "status": row.status, "subnet_id": subnet_id,
                "subnet": f"{sub.network}/{sub.prefix}", "device_id": device_id, "used_as": role}

    async def save_address(self, address: str, status: str, subnet_id: Optional[int] = None,
                            device_id: Optional[int] = None, used_as: Optional[str] = None,
                            remark: Optional[str] = None, operator: Optional[str] = None) -> IpAddress:
        address = (address or "").strip()
        if not address:
            raise ValueError("\u8bf7\u586b\u5199 IP \u5730\u5740")
        if status not in IP_STATUS:
            raise ValueError("\u72b6\u6001\u975e\u6cd5")
        try:
            ipaddress.ip_address(address.split("%")[0])
        except ValueError:
            raise ValueError("IP \u683c\u5f0f\u4e0d\u6b63\u786e")
        if subnet_id:
            raw = (await self.db.execute(select(IpSubnet).where(IpSubnet.id == subnet_id))).scalar_one_or_none()
            if not raw:
                raise ValueError("\u5b50\u7f51\u4e0d\u5b58\u5728")
            try:
                if ipaddress.ip_address(address.split("%")[0]) not in ipaddress.ip_network(f"{raw.network}/{raw.prefix}", strict=False):
                    raise ValueError("\u8be5 IP \u4e0d\u5c5e\u4e8e\u6240\u9009\u5b50\u7f51")
            except ValueError:
                raise ValueError("\u8be5 IP \u4e0d\u5c5e\u4e8e\u6240\u9009\u5b50\u7f51")

        row = (await self.db.execute(select(IpAddress).where(IpAddress.address == address))).scalar_one_or_none()
        if row:
            # \u5206\u914d\u524d\u9632\u51b2\u7a81\uff1a\u5c06\u67d0 IP \u6807\u8bb0\u4e3a allocated \u4e14\u7ed1\u5b9a\u8bbe\u5907\u65f6\u8fdb\u884c\u5355\u4e00\u5360\u7528\u6821\u9a8c
            from_value = row.status
            old_device = row.device_id
            if status == "allocated" and device_id and row.device_id != device_id:
                await validate_no_conflict(self.db, address, exclude_address=address, exclude_device_id=device_id)
            row.status = status
            row.subnet_id = subnet_id if subnet_id is not None else row.subnet_id
            row.device_id = device_id
            row.used_as = used_as
            if remark is not None:
                row.remark = remark
            await self.db.flush()
            await self.db.refresh(row)
            if from_value != status or old_device != device_id:
                write_ip_history(self.db, row.id, address, "status" if from_value != status else "device",
                                 from_value if from_value != status else str(old_device),
                                 status if from_value != status else str(device_id),
                                 operator=operator, source="manual")
            return row
        if status == "allocated" and device_id:
            await validate_no_conflict(self.db, address, exclude_address=address, exclude_device_id=device_id)
        row = IpAddress(address=address, status=status, subnet_id=subnet_id, device_id=device_id,
                        used_as=used_as, remark=remark)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        to_val = (str(device_id) if device_id else None) or status or None
        write_ip_history(self.db, row.id, address, "device", None, to_val,
                         operator=operator, source="manual")
        return row

    async def list_history(self, address: Optional[str] = None, address_id: Optional[int] = None,
                           page: int = 1, page_size: int = 20) -> tuple[list, int]:
        """\u67e5\u8be2 IP \u53f0\u8d26\u53d8\u66f4\u5386\u53f2\uff0c\u53ef\u6309 IP \u5730\u5740\u6216\u53f0\u8d26 ID \u8fc7\u6ee4\uff0c\u6309\u65f6\u95f4\u5012\u5e8f\u3002"""
        conds = []
        if address:
            conds.append(IpAddressHistory.address == address)
        if address_id:
            conds.append(IpAddressHistory.ip_id == address_id)
        base = select(IpAddressHistory).where(*conds) if conds else select(IpAddressHistory)
        total = (await self.db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
        rows = (await self.db.execute(
            base.order_by(IpAddressHistory.created_at.desc(), IpAddressHistory.id.desc())
            .offset((page - 1) * page_size).limit(page_size)
        )).scalars().all()
        items = [{
            "id": r.id, "ip_id": r.ip_id, "address": r.address, "field_changed": r.field_changed,
            "from_value": r.from_value, "to_value": r.to_value, "operator": r.operator,
            "source": r.source, "remark": r.remark, "created_at": r.created_at,
        } for r in rows]
        return items, total

    async def delete_address(self, address_id: int) -> bool:
        row = (await self.db.execute(select(IpAddress).where(IpAddress.id == address_id))).scalar_one_or_none()
        if not row:
            return False
        await self.db.delete(row)
        await self.db.flush()
        return True

    async def import_device_ips(self) -> dict:
        """\u81ea\u52a8\u628a\u8bbe\u5907\u7684\u7ba1\u7406/\u4e1a\u52a1/\u5e26\u5916 IP \u767b\u8bb0\u5230\u5339\u914d\u5b50\u7f51\u7684\u53f0\u8d26\u3002
        \u76f8\u540c IP \u5df2\u88ab\u5176\u4ed6\u8bbe\u5907\u5360\u7528\u65f6\u8df3\u8fc7\u5e76\u8bb0\u5f55\u4e3a skipped\u3002"""
        rows = (await self.db.execute(
            select(Device.id, Device.name, Device.management_ip, Device.business_ip, Device.out_of_band_ip)
        )).all()
        subnets = (await self.db.execute(select(IpSubnet))).scalars().all()
        nets = []
        for sub in subnets:
            try:
                nets.append((sub, ipaddress.ip_network(f"{sub.network}/{sub.prefix}", strict=False)))
            except Exception:
                continue

        def _to_bytes(s):
            try:
                return int(ipaddress.ip_address(s.split("%")[0]))
            except Exception:
                return None

        added = 0
        skipped = 0
        for r in rows:
            fields = [("management_ip", "management"), ("business_ip", "business"), ("out_of_band_ip", "oob")]
            for attr, role in fields:
                raw = getattr(r, attr)
                if not raw:
                    continue
                for part in str(raw).replace(";", ",").replace("\uff0c", ",").split(","):
                    addr = part.strip()
                    if not addr:
                        continue
                    iaddr = _to_bytes(addr)
                    target = None
                    for sub, net in nets:
                        if iaddr is not None and int(net.network_address) <= iaddr <= int(net.network_address + net.num_addresses - 1):
                            target = sub
                            break
                    row = (await self.db.execute(select(IpAddress).where(IpAddress.address == addr))).scalar_one_or_none()
                    if row:
                        if row.status == "free":
                            row.status = "allocated"; row.device_id = r.id; row.used_as = role
                            if target is not None:
                                row.subnet_id = target.id
                            write_ip_history(self.db, row.id, addr, "device", None, str(r.id),
                                             operator="system", source="device_sync")
                            added += 1
                        else:
                            if row.device_id != r.id:
                                skipped += 1
                        continue
                    row = IpAddress(address=addr, status="allocated", device_id=r.id, used_as=role,
                                    subnet_id=target.id if target else None)
                    self.db.add(row)
                    added += 1
                    write_ip_history(self.db, None, addr, "device", None, str(r.id),
                                     operator="system", source="device_sync")
        await self.db.flush()
        return {"added": added, "skipped": skipped}

_SYNC_ROLE_FIELDS = [("management_ip", "management"), ("business_ip", "business"), ("out_of_band_ip", "oob")]


async def sync_device_ip_ledger(db, device, operator: str = None) -> dict:
    """\u5c06\u8bbe\u5907\u7684 IP \u5b57\u6bb5\uff08management/business/oob\uff09\u81ea\u52a8\u540c\u6b65\u5230 IP \u53f0\u8d26\uff0c
    \u4fdd\u8bc1\u8bbe\u5907\u4e3a\u552f\u4e00\u4e8b\u5b9e\u6e90\uff0c\u53f0\u8d26\u968f\u8bbe\u5907\u53d8\u66f4\u5728\u540c\u4e00\u4e8b\u52a1\u5185\u81ea\u52a8\u66f4\u65b0\u3002
    - \u65b0\u589e/\u4fee\u6539\u8bbe\u5907 IP \u65f6\uff0c\u81ea\u52a8\u5c06\u5bf9\u5e94\u53f0\u8d26\u6807\u8bb0\u4e3a allocated \u5e76\u6302\u7ed1\u8bbe\u5907\u3002
    - \u5df2\u88ab\u4ed6\u8bbe\u5907\u5360\u7528\u7684 IP \u4e0d\u81ea\u52a8\u62a2\u5360\uff0c\u800c\u662f\u8bb0\u4e3a conflict \u8df3\u8fc7\u3002
    - \u79fb\u9664\u8bbe\u5907 IP \u65f6\uff0c\u91ca\u653e\u539f\u5148\u5f52\u5c5e\u8be5\u8bbe\u5907\u4e14\u4e0d\u518d\u4f7f\u7528\u7684 IP \uff08\u6807\u8bb0 free\uff09\u3002
    - \u4e0d\u4f1a\u91ca\u653e\u5df2\u88ab\u5176\u4ed6\u8bbe\u5907\u5360\u7528\u6216\u624b\u52a8\u9884\u7559\u7684 IP\uff0c\u907f\u514d\u8986\u76d6\u4eba\u5de5\u7f16\u8f91\u3002
    """
    if device is None:
        return {"added": 0, "updated": 0, "released": 0, "conflict": 0}

    wanted = []
    seen_addrs = set()
    for attr, role in _SYNC_ROLE_FIELDS:
        raw = getattr(device, attr, None)
        if not raw:
            continue
        for part in str(raw).replace(";", ",").replace("\uff0c", ",").split(","):
            addr = part.strip()
            if not addr:
                continue
            if addr in seen_addrs:
                continue
            seen_addrs.add(addr)
            wanted.append((addr, role))

    subnets = (await db.execute(select(IpSubnet))).scalars().all()
    nets = []
    for sub in subnets:
        try:
            nets.append((sub, ipaddress.ip_network(f"{sub.network}/{sub.prefix}", strict=False)))
        except Exception:
            continue

    def _match_subnet(addr):
        try:
            iaddr = int(ipaddress.ip_address(addr.split("%")[0]))
        except Exception:
            return None
        for sub, net in nets:
            if int(net.network_address) <= iaddr <= int(net.network_address + net.num_addresses - 1):
                return sub
        return None

    held = {}
    for row in (await db.execute(
        select(IpAddress).where(IpAddress.device_id == device.id, IpAddress.status == "allocated")
    )).scalars().all():
        held[row.address] = row

    added = 0
    updated = 0
    released = 0
    conflict = 0
    wanted_map = dict(wanted)

    for addr, role in wanted:
        row = held.get(addr)
        if row is None:
            row = (await db.execute(select(IpAddress).where(IpAddress.address == addr))).scalar_one_or_none()
        sub = _match_subnet(addr)
        if row is None:
            db.add(IpAddress(address=addr, status="allocated", device_id=device.id, used_as=role,
                             subnet_id=sub.id if sub else None))
            added += 1
            write_ip_history(db, None, addr, "device", None, str(device.id), operator=operator, source="device_sync")
        else:
            # \u5148\u5f00\u5927\u96f7\u963b\uff1a\u5982\u679c\u8be5 IP \u5df2\u88ab\u5176\u4ed6\u8bbe\u5907\u5360\u7528\uff0c\u4e0d\u81ea\u52a8\u62a2\u5360
            if row.status == "allocated" and row.device_id is not None and row.device_id != device.id:
                conflict += 1
                continue
            from_status = row.status
            from_device = row.device_id
            if row.status != "allocated":
                row.status = "allocated"
            row.device_id = device.id
            row.used_as = role
            if sub is not None:
                row.subnet_id = sub.id
            if from_status != "allocated" or from_device != device.id:
                write_ip_history(db, row.id, addr, "status" if from_status != "allocated" else "device",
                                 from_status if from_status != "allocated" else str(from_device),
                                 "allocated" if from_status != "allocated" else str(device.id),
                                 operator=operator, source="device_sync")
            updated += 1

    for addr, row in held.items():
        if addr not in wanted_map and row is not None and row.device_id == device.id:
            if row.status == "allocated":
                write_ip_history(db, row.id, addr, "status", "allocated", "free",
                                 operator=operator, source="device_sync")
            row.status = "free"
            row.device_id = None
            row.used_as = None
            released += 1

    await db.flush()
    return {"added": added, "updated": updated, "released": released, "conflict": conflict}


async def release_device_ip_ledger(db, device_id, operator: str = None) -> int:
    """\u5220\u9664\u8bbe\u5907\u65f6\uff0c\u91ca\u653e\u8be5\u8bbe\u5907\u5728 IP \u53f0\u8d26\u4e2d\u5360\u7528\u7684\u6240\u6709\u6761\u76ee\uff0c\u5e76\u7559\u74e3\u53d8\u66f4\u5386\u53f2\u3002"""
    rows = (await db.execute(
        select(IpAddress).where(IpAddress.device_id == device_id)
    )).scalars().all()
    n = 0
    for row in rows:
        if row.status == "allocated":
            write_ip_history(db, row.id, row.address, "status", "allocated", "free",
                             operator=operator or "system", source="release")
        row.device_id = None
        if row.status == "allocated":
            row.status = "free"
            row.used_as = None
        n += 1
    if n:
        await db.flush()
    return n
