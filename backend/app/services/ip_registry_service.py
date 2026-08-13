"""IP 地址台账与子网管理服务。

在原有“基于设备字段实时聚合”之上，增加：
- 子网定义管理（网段/掩码/网关/VLAN）；
- IP 台账条目（分配/预留/空闲状态、归属设备）；
- 子网使用率与剩余容量统计；
- 从设备字段自动导入 IP 到台账。
"""
import ipaddress
from typing import Optional

from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ip_address import IpSubnet, IpAddress
from app.models.device import Device


IP_STATUS = {"free", "reserved", "allocated"}


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
        result = await self.db.execute(select(IpSubnet).order_by(IpSubnet.network, IpSubnet.prefix))
        subnets = result.scalars().all()
        # 汇总各子网已用条目
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

        out = []
        for sub in subnets:
            capacity = _capacity(sub)
            alloc = used.get(sub.id, {}).get("allocated", 0)
            resv = used.get(sub.id, {}).get("reserved", 0)
            free = max(capacity - alloc - resv, 0) if capacity else 0
            usage = (alloc + resv) / capacity * 100 if capacity else 0
            out.append({
                "id": sub.id,
                "name": sub.name,
                "network": sub.network,
                "prefix": sub.prefix,
                "cidr": f"{sub.network}/{sub.prefix}",
                "gateway": sub.gateway,
                "vlan": sub.vlan,
                "description": sub.description,
                "status": sub.status,
                "capacity": capacity,
                "allocated": alloc,
                "reserved": resv,
                "free": free,
                "usage": round(usage, 2),
            })
        return out

    async def create_subnet(self, name, network, prefix, gateway=None, vlan=None, description=None, status="active") -> IpSubnet:
        # 校验 CIDR
        try:
            net = ipaddress.ip_network(f"{network}/{prefix}", strict=False)
            network = str(net.network_address)
        except ValueError as e:
            raise ValueError(f"网段格式不正确: {e}")
        exists = (await self.db.execute(select(IpSubnet).where(IpSubnet.network == network, IpSubnet.prefix == prefix))).scalar_one_or_none()
        if exists:
            raise ValueError("该网段已存在")
        sub = IpSubnet(name=name, network=network, prefix=prefix, gateway=gateway, vlan=vlan, description=description, status=status)
        self.db.add(sub)
        await self.db.flush()
        await self.db.refresh(sub)
        return sub

    async def update_subnet(self, subnet_id: int, name=None, gateway=None, vlan=None, description=None, status=None) -> Optional[IpSubnet]:
        sub = (await self.db.execute(select(IpSubnet).where(IpSubnet.id == subnet_id))).scalar_one_or_none()
        if not sub:
            return None
        if name is not None: sub.name = name
        if gateway is not None: sub.gateway = gateway
        if vlan is not None: sub.vlan = vlan
        if description is not None: sub.description = description
        if status is not None: sub.status = status
        await self.db.flush()
        await self.db.refresh(sub)
        return sub

    async def delete_subnet(self, subnet_id: int) -> bool:
        sub = (await self.db.execute(select(IpSubnet).where(IpSubnet.id == subnet_id))).scalar_one_or_none()
        if not sub:
            return False
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

    async def save_address(self, address: str, status: str, subnet_id: Optional[int] = None, device_id: Optional[int] = None, used_as: Optional[str] = None, remark: Optional[str] = None) -> IpAddress:
        if status not in IP_STATUS:
            raise ValueError("状态非法")
        try:
            ipaddress.ip_address(address.split("%")[0])
        except ValueError:
            raise ValueError("IP 格式不正确")
        # 若指定子网，确保地址属于该网段
        if subnet_id:
            sub = (await self.db.execute(select(IpSubnet).where(IpSubnet.id == subnet_id))).scalar_one_or_none()
            if not sub:
                raise ValueError("子网不存在")
            try:
                if ipaddress.ip_address(address.split("%")[0]) not in ipaddress.ip_network(f"{sub.network}/{sub.prefix}", strict=False):
                    raise ValueError("该 IP 不属于所选子网")
            except ValueError:
                raise ValueError("该 IP 不属于所选子网")

        row = (await self.db.execute(select(IpAddress).where(IpAddress.address == address))).scalar_one_or_none()
        if row:
            row.status = status
            row.subnet_id = subnet_id if subnet_id is not None else row.subnet_id
            row.device_id = device_id
            row.used_as = used_as
            if remark is not None: row.remark = remark
            await self.db.flush()
            await self.db.refresh(row)
            return row
        row = IpAddress(address=address, status=status, subnet_id=subnet_id, device_id=device_id, used_as=used_as, remark=remark)
        self.db.add(row)
        await self.db.flush()
        await self.db.refresh(row)
        return row

    async def delete_address(self, address_id: int) -> bool:
        row = (await self.db.execute(select(IpAddress).where(IpAddress.id == address_id))).scalar_one_or_none()
        if not row:
            return False
        await self.db.delete(row)
        await self.db.flush()
        return True

    async def import_device_ips(self) -> dict:
        """自动把设备的管理/业务/带外 IP 登记到匹配子网的台账。"""
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
                out = int(ipaddress.ip_address(s.split("%")[0]))
                return out
            except Exception:
                return None

        import json
        added = 0
        skipped = 0
        for r in rows:
            fields = [("management_ip", "management"), ("business_ip", "business"), ("out_of_band_ip", "oob")]
            for attr, role in fields:
                raw = getattr(r, attr)
                if not raw:
                    continue
                for part in str(raw).replace(";", ",").replace("，", ",").split(","):
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
                            row.status = "allocated"; row.device_id = r.id; row.used_as = role; row.subnet_id = target.id if target else row.subnet_id; added += 1
                        else:
                            skipped += 1
                        continue
                    row = IpAddress(address=addr, status="allocated", device_id=r.id, used_as=role, subnet_id=target.id if target else None)
                    self.db.add(row); added += 1
        await self.db.flush()
        return {"added": added, "skipped": skipped}

_SYNC_ROLE_FIELDS = [("management_ip", "management"), ("business_ip", "business"), ("out_of_band_ip", "oob")]


async def sync_device_ip_ledger(db, device) -> dict:
    """\u5c06\u8bbe\u5907\u7684 IP \u5b57\u6bb5\uff08management/business/oob\uff09\u81ea\u52a8\u540c\u6b65\u5230 IP \u53f0\u8d26\uff0c
    \u4fdd\u8bc1\u8bbe\u5907\u4e3a\u552f\u4e00\u4e8b\u5b9e\u6e90\uff0c\u53f0\u8d26\u968f\u8bbe\u5907\u53d8\u66f4\u5728\u540c\u4e00\u4e8b\u52a1\u5185\u81ea\u52a8\u66f4\u65b0\u3002
    - \u65b0\u589e/\u4fee\u6539\u8bbe\u5907 IP \u65f6\uff0c\u81ea\u52a8\u5c06\u5bf9\u5e94\u53f0\u8d26\u6807\u8bb0\u4e3a allocated \u5e76\u6302\u7ed1\u8bbe\u5907\u3002
    - \u79fb\u9664\u8bbe\u5907 IP \u65f6\uff0c\u91ca\u653e\u539f\u5148\u5f52\u5c5e\u8be5\u8bbe\u5907\u4e14\u4e0d\u518d\u4f7f\u7528\u7684 IP \uff08\u6807\u8bb0 free\uff09\u3002
    - \u4e0d\u4f1a\u91ca\u653e\u5df2\u88ab\u5176\u4ed6\u8bbe\u5907\u5360\u7528\u6216\u624b\u52a8\u9884\u7559\u7684 IP\uff0c\u907f\u514d\u8986\u76d6\u4eba\u5de5\u7f16\u8f91\u3002
    """
    if device is None:
        return {"added": 0, "released": 0}

    # 1) \u89e3\u6790\u8bbe\u5907\u5f53\u524d\u6240\u6709 IP -> (ip, role)
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

    # 2) \u83b7\u53d6\u6240\u6709\u5b50\u7f51\u7528\u4e8e\u5339\u914d subnet_id
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

    # 3) \u51c6\u5907\u5f53\u524d\u53f0\u8d26\u4e2d\u5f52\u5c5e\u8be5\u8bbe\u5907\u7684 IP
    held = {}
    for row in (await db.execute(
        select(IpAddress).where(IpAddress.device_id == device.id, IpAddress.status == "allocated")
    )).scalars().all():
        held[row.address] = row

    added = 0
    updated = 0
    released = 0
    wanted_map = dict(wanted)

    # 4) upsert \u5f53\u524d\u7528\u4e8e\u7684 IP
    for addr, role in wanted:
        row = held.get(addr)
        if row is None:
            row = (await db.execute(select(IpAddress).where(IpAddress.address == addr))).scalar_one_or_none()
        sub = _match_subnet(addr)
        if row is None:
            db.add(IpAddress(address=addr, status="allocated", device_id=device.id, used_as=role, subnet_id=sub.id if sub else None))
            added += 1
        else:
            if row.status != "allocated":
                # \u8bbe\u5907\u5148\u4f7f\u7528 -> \u6807\u8bb0 allocated\uff1b\u4f46\u4e0d\u91ca\u653e\u522b\u4eba\u7684\u9884\u7559
                row.status = "allocated"
            row.device_id = device.id
            row.used_as = role
            if sub is not None:
                row.subnet_id = sub.id
            updated += 1

    # 5) \u91ca\u653e\u88ab\u79fb\u9664\u7684 IP\uff08\u4ec5\u5f53\u4ecd\u5f52\u5c5e\u672c\u8bbe\u5907\u4e14\u4e0d\u518d\u4f7f\u7528\uff09
    for addr, row in held.items():
        if addr not in wanted_map and row is not None and row.device_id == device.id:
            # \u4ec5\u91ca\u653e\u5f53\u524d\u8bbe\u5907\u81ea\u52a8\u7ef4\u62a4\u7684 allocated\uff0c\u4fdd\u7559\u624b\u52a8\u9884\u7559/beans\u8bb0
            row.status = "free"
            row.device_id = None
            row.used_as = None
            released += 1

    await db.flush()
    return {"added": added, "updated": updated, "released": released}


async def release_device_ip_ledger(db, device_id) -> int:
    """\u5220\u9664\u8bbe\u5907\u65f6\uff0c\u91ca\u653e\u8be5\u8bbe\u5907\u5728 IP \u53f0\u8d26\u4e2d\u5360\u7528\u7684\u6240\u6709\u6761\u76ee\u3002"""
    rows = (await db.execute(
        select(IpAddress).where(IpAddress.device_id == device_id)
    )).scalars().all()
    n = 0
    for row in rows:
        row.device_id = None
        if row.status == "allocated":
            row.status = "free"
            row.used_as = None
        n += 1
    if n:
        await db.flush()
    return n
