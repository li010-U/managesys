"""AI assistant write-tools: intent parsing + confirmed execution.

Write tools never run from raw LLM output. chat.py parses the user
request into a proposal, the UI asks the human to confirm, and only the
confirmed execute() path (permission-checked) runs the operation.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

class PermissionDeniedError(Exception):
    pass

TOOLS: Dict[str, Dict[str, Any]] = {
    "create_work_order": {"permission": "work:create", "required": ["title"],
        "optional": ["description", "priority", "device_id", "facility_id"]},
    "handle_alert": {"permission": "monitor:handle_alert", "required": ["alert_id", "action_type"],
        "optional": ["remark", "root_cause"]},
    "assign_work_order": {"permission": "work:edit", "required": ["order_id", "assignee_username"],
        "optional": ["remark"]},
    "close_work_order": {"permission": "work:edit", "required": ["order_id"],
        "optional": ["remark"]},
    "verify_work_order": {"permission": "work:edit", "required": ["order_id", "satisfaction", "accept"],
        "optional": ["feedback"]},
    "mount_device": {"permission": "device:mount", "required": ["device_id", "rack_id"],
        "optional": ["remark"]},
    "unmount_device": {"permission": "device:unmount", "required": ["device_id"],
        "optional": ["remark"]},
    "create_alert_rule": {"permission": "monitor:config_rule",
        "required": ["name", "code", "metric", "condition", "threshold"],
        "optional": ["alert_level", "enabled", "notify_methods"]},
}

_VALID_ALERT_ACTIONS = {"acknowledge", "resolve", "ignore"}
_VALID_PRIORITIES = {"low", "normal", "high", "urgent"}
_VALID_CONDITIONS = {"gt", "lt", "gte", "lte", "eq"}
_VALID_LEVELS = {"general", "serious", "emergency"}

def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise ValueError(msg)

def _ensure_permission(current_user, permission: str) -> None:
    from app.core.deps import has_permission
    if not has_permission(current_user, permission):
        raise PermissionDeniedError("permission:" + permission)

def _device_u_size(device) -> int:
    s = getattr(device, "start_u", None)
    e = getattr(device, "end_u", None)
    if s is not None and e is not None:
        size = e - s + 1
        return size if size > 0 else 1
    return 1

def _detect_alert_id(text: str) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(?:#|id\s*[:=]?\s*)(\d+)", text, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"alert(?:\s+(?:num|number)?)?\s*[:=]?\s*(\d+)", text, flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None

def _detect_action_type(text: str) -> Optional[str]:
    low = (text or "").lower()
    kws = ["resolve", "resolved"]
    kws.append("\u89e3\u51b3")
    if any(k in low for k in kws):
        return "resolve"
    kwa = ["acknowledge", "accepted"]
    kwa.append("\u786e\u8ba4")
    kwa.append("\u5df2\u77e5\u6089")
    if any(k in low for k in kwa):
        return "acknowledge"
    kwi = ["ignore"]
    kwi.append("\u5ffd\u7565")
    if any(k in low for k in kwi):
        return "ignore"
    return None
GONGDAN = "\u5de5\u5355"
ASSIGN = "\u5206\u914d"  # ??
PAIPAI = "\u6307\u6d3e"  # ??
CLOSE = "\u5173\u95ed"  # ??
VERIFY = "\u9a8c\u6536"  # ??
MOUNT = "\u6302\u8f7d"  # ??
SHANGJIA = "\u4e0a\u67b6"  # ??
UNMOUNT = "\u5378\u8f7d"  # ??
XIAJIA = "\u4e0b\u67b6"  # ??
RULE = "\u89c4\u5219"  # ??
RULE2 = "\u544a\u8b66\u89c4\u5219"  # ????
ADD = "\u6dfb\u52a0"  # ??
XINZENG = "\u65b0\u589e"  # ??
GIVE = "\u7ed9"  # ?
TOU = "\u5934"  # ?(??)
PASS = "\u901a\u8fc7"  # ??(??)
REJ = "\u9a73\u56de"  # ??(??)
INTO = "\u5230"  # ? (?????)

def _find_order_id(text: str) -> Optional[int]:
    m = re.search(r"(?:#|id\s*[:=]?)\s*(\d+)", text or "", flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(GONGDAN + r"\s*(\d+)", text or "")
    if m:
        return int(m.group(1))
    return None

def _find_dev_id(text: str) -> Optional[int]:
    m = re.search(r"(?:#|id\s*[:=]?)\s*(\d+)", text or "", flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    m = re.search(r"\u8bbe\u5907\s*(?:#|\u7f16\u53f7)?\s*(\d+)", text or "")
    if m:
        return int(m.group(1))
    return None

def _find_rack_id(text: str) -> Optional[int]:
    m = re.search(r"(?:\u673a\u67dc)\s*(?:#|\u7f16\u53f7)?\s*(\d+)", text or "")
    if m:
        return int(m.group(1))
    m = re.search(r"rack\s*(?:#)?\s*(\d+)", text or "", flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None

def _find_assignee(text: str) -> Optional[str]:
    # username is the token right after the "give" particle (?) or assign to
    m = re.search(r"\u7ed9\s*([^\s,\u3001\uff0c\u3002]+)", text or "")
    if m:
        return m.group(1).strip("\u3001\uff0c\u3002")
    m = re.search(r"assign\s+to\s+([^\s,\u3001\uff0c\u3002]+)", text or "", flags=re.IGNORECASE)
    if m:
        return m.group(1).strip("\u3001\uff0c\u3002")
    m = re.search(r"\bto\s+([A-Za-z0-9_\.\-]+)", text or "")
    if m:
        return m.group(1)
    return None
def _detect_score(text: str) -> Optional[int]:
    m = re.search(r"\u6ee1\u610f\u5ea6\s*[:=]?\s*(\d+)", text or "")
    if m:
        return int(m.group(1))
    m = re.search(r"score\s*[:=]?\s*(\d+)", text or "", flags=re.IGNORECASE)
    if m:
        return int(m.group(1))
    return None

def _detect_accept(text: str) -> Optional[bool]:
    if re.search(PASS + "|accept|ok", text or "", flags=re.IGNORECASE):
        return True
    if re.search(REJ + "|reject|fail", text or "", flags=re.IGNORECASE):
        return False
    return None

def _extract_alert_rule(text: str):
    """Best-effort extract a few alert rule fields from free text."""
    m = re.search(r"(?:name|" + RULE + r")\s*[:=]\s*(\S+)", text or "")
    name = m.group(1) if m else ("\u65b0\u544a\u8b66\u89c4\u5219")
    metric = "temperature"
    if re.search("cpu|\u5728\u7ebf\u7387", text or "", flags=re.IGNORECASE):
        metric = "cpu"
    condition = "gt"
    mt = re.search(r"(?:\u8d85\u8fc7|>|\u5927\u4e8e)\s*(\d+)", text or "")
    threshold = float(mt.group(1)) if mt else 80.0
    return {"name": name, "code": "rule_" + str(len(text or "")), "metric": metric,
            "condition": condition, "threshold": threshold}

def parse_proposal(user_text: str, answer_text: str = "") -> Optional[Dict[str, Any]]:
    combined = "{0} {1}".format(user_text or "", answer_text or "").strip()
    if not combined:
        return None
    u = user_text or ""

    # create work order
    if re.search(r"(?:\u521b\u5efa|\u65b0\u5efa|\u4e0b\u5355|open|create)\s*(?:\u4e00\u5f20|\u4e2a)?\s*" + GONGDAN, combined, flags=re.IGNORECASE):
        title_m = re.search(r"\u6807\u9898\s*[:=]\s*(.+)", u)
        title = None
        if title_m:
            title = title_m.group(1).strip()
        if not title:
            first_line = next((ln for ln in u.splitlines() if ln.strip()), "")
            title = re.sub(r"\u521b\u5efa.*?" + GONGDAN, "", first_line).strip()
            title = (title or GONGDAN)[:40]
        priority = "normal"
        if re.search(r"\u7d27\u6025|urgent", combined, flags=re.IGNORECASE):
            priority = "urgent"
        elif re.search(r"\u9ad8|high", combined, flags=re.IGNORECASE):
            priority = "high"
        elif re.search(r"\u4f4e|low", combined, flags=re.IGNORECASE):
            priority = "low"
        return {"tool": "create_work_order", "label": "create_work_order",
                "args": {"title": title, "description": None, "priority": priority,
                         "device_id": None, "facility_id": None}}

    # handle alert
    action = _detect_action_type(combined)
    alert_id = _detect_alert_id(combined)
    if action and alert_id is not None:
        remark = None
        rm = re.search(r"(?:remark|\u5907\u6ce8)\s*[:=]\s*(.+)", combined)
        if rm:
            remark = rm.group(1).strip() or None
        return {"tool": "handle_alert", "label": "handle_alert",
                "args": {"alert_id": alert_id, "action_type": action,
                         "remark": remark, "root_cause": None}}

    # assign work order: assign/paipai + order id + assignee
    if re.search(ASSIGN + "|" + PAIPAI + "|assign", combined, flags=re.IGNORECASE) and (GONGDAN in combined or "work order" in combined.lower()):
        oid = _find_order_id(combined)
        who = _find_assignee(combined)
        if oid is not None and who:
            return {"tool": "assign_work_order", "label": "assign_work_order",
                    "args": {"order_id": oid, "assignee_username": who, "remark": None}}

    # close work order
    if (CLOSE + GONGDAN) in combined or re.search(r"close(?:\s+|\b)" + GONGDAN, combined, flags=re.IGNORECASE):
        oid = _find_order_id(combined)
        if oid is not None:
            return {"tool": "close_work_order", "label": "close_work_order",
                    "args": {"order_id": oid, "remark": None}}

    # verify work order
    if (VERIFY + GONGDAN) in combined or re.search(r"accept\s*" + GONGDAN, combined, flags=re.IGNORECASE):
        oid = _find_order_id(combined)
        if oid is not None:
            score = _detect_score(combined)
            ok = _detect_accept(combined)
            if ok is not None:
                return {"tool": "verify_work_order", "label": "verify_work_order",
                        "args": {"order_id": oid, "satisfaction": score or 5, "accept": ok, "feedback": None}}

    # mount device
    if re.search(MOUNT + "|" + SHANGJIA + "|mount", combined, flags=re.IGNORECASE) and "\u8bbe\u5907" in combined:
        did = _find_dev_id(combined)
        rid = _find_rack_id(combined)
        if did is not None and rid is not None:
            return {"tool": "mount_device", "label": "mount_device",
                    "args": {"device_id": did, "rack_id": rid, "remark": None}}

    # unmount device
    if re.search(UNMOUNT + "|" + XIAJIA + "|unmount", combined, flags=re.IGNORECASE) and "\u8bbe\u5907" in combined:
        did = _find_dev_id(combined)
        if did is not None:
            return {"tool": "unmount_device", "label": "unmount_device",
                    "args": {"device_id": did, "remark": None}}

    # create alert rule: add/xinzen + rule keywords
    if re.search(ADD + "|" + XINZENG, combined, flags=re.IGNORECASE) and RULE in combined:
        r = _extract_alert_rule(combined)
        return {"tool": "create_alert_rule", "label": "create_alert_rule", "args": r}

    return None

async def execute(db: AsyncSession, tool: str, args: Dict[str, Any], current_user) -> Dict[str, Any]:
    """Run a confirmed, permission-checked write tool. current_user is a User-like object."""
    spec = TOOLS.get(tool)
    if not spec:
        raise ValueError("Unknown tool: " + str(tool))
    _ensure_permission(current_user, spec["permission"])
    operator = getattr(current_user, "username", "system")
    if tool == "create_work_order":
        return await _exec_create_work_order(db, args, operator)
    if tool == "handle_alert":
        return await _exec_handle_alert(db, args, operator)
    if tool == "assign_work_order":
        return await _exec_assign_work_order(db, args, current_user)
    if tool == "close_work_order":
        return await _exec_close_work_order(db, args, current_user)
    if tool == "verify_work_order":
        return await _exec_verify_work_order(db, args, current_user)
    if tool == "mount_device":
        return await _exec_mount_device(db, args, current_user)
    if tool == "unmount_device":
        return await _exec_unmount_device(db, args, current_user)
    if tool == "create_alert_rule":
        return await _exec_create_alert_rule(db, args, operator)
    raise ValueError("Unknown tool: " + str(tool))


async def _get_work_order(db, oid: int):
    from app.db.compat_sql import exec_sql
    row = (await exec_sql(db, "SELECT id, title, status, creator_id, assignee_id FROM work_orders WHERE id = ?", (oid,))).fetchone()
    return row


def _ensure_owner(current_user, creator_id):
    is_owner = getattr(current_user, "is_super_admin", False) or (getattr(current_user, "id", None) == creator_id)
    if not is_owner:
        raise PermissionDeniedError("only creator or super admin can do this")


async def _exec_assign_work_order(db, args, current_user):
    from sqlalchemy import select
    from app.models import User
    from app.db.retry import with_commit_retry
    from app.db.compat_sql import exec_sql
    oid = int(args.get("order_id"))
    who = str(args.get("assignee_username") or "").strip()
    _require(bool(who), "assignee_username is required")
    row = await _get_work_order(db, oid)
    _require(row is not None, "work order not found")
    _require(row.status in {"pending", "assigned", "processing"}, "cannot assign work order in status " + str(row.status))
    res = await db.execute(select(User).where(User.username == who))
    assignee = res.scalar_one_or_none()
    _require(assignee is not None, "assignee user not found: " + who)
    remark = args.get("remark")
    await exec_sql(db, "UPDATE work_orders SET assignee_id = ?, status = \x27assigned\x27 WHERE id = ?", (assignee.id, oid))
    await exec_sql(db, "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
                  (oid, current_user.id, "assigned by AI to " + who, "process"))
    await with_commit_retry(db.commit)
    return {"tool": "assign_work_order", "result": "assigned", "order_id": oid, "assignee": who}


async def _exec_close_work_order(db, args, current_user):
    from app.db.retry import with_commit_retry
    from app.db.compat_sql import exec_sql
    oid = int(args.get("order_id"))
    row = await _get_work_order(db, oid)
    _require(row is not None, "work order not found")
    _ensure_owner(current_user, row.creator_id)
    remark = args.get("remark")
    await exec_sql(db, "UPDATE work_orders SET status = \x27closed\x27 WHERE id = ?", (oid,))
    await exec_sql(db, "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
                  (oid, current_user.id, remark or "closed by AI", "close"))
    await with_commit_retry(db.commit)
    return {"tool": "close_work_order", "result": "closed", "order_id": oid}


async def _exec_verify_work_order(db, args, current_user):
    from app.db.retry import with_commit_retry
    from app.db.compat_sql import exec_sql
    oid = int(args.get("order_id"))
    row = await _get_work_order(db, oid)
    _require(row is not None, "work order not found")
    _ensure_owner(current_user, row.creator_id)
    try:
        score = int(args.get("satisfaction"))
    except (TypeError, ValueError):
        raise ValueError("satisfaction must be 1-5")
    _require(1 <= score <= 5, "satisfaction must be 1-5")
    accept = bool(args.get("accept"))
    feedback = args.get("feedback")
    new_status = "completed" if accept else "processing"
    await exec_sql(db, "UPDATE work_orders SET status = ?, satisfaction = ?, feedback = ? WHERE id = ?",
                  (new_status, score, feedback, oid))
    await exec_sql(db, "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
                  (oid, current_user.id, ("accept" if accept else "reject") + " by AI, score " + str(score), "verify"))
    await with_commit_retry(db.commit)
    return {"tool": "verify_work_order", "result": "accepted" if accept else "rejected", "order_id": oid, "satisfaction": score}

async def _exec_mount_device(db, args, current_user):
    from sqlalchemy import select
    from app.models import Device, Rack, DeviceLifecycle
    from app.db.retry import with_commit_retry
    from app.services.audit_service import AuditService
    did = int(args.get("device_id"))
    rid = int(args.get("rack_id"))
    remark = args.get("remark")
    dev = (await db.execute(select(Device).where(Device.id == did))).scalar_one_or_none()
    _require(dev is not None, "device not found: " + str(did))
    rack = (await db.execute(select(Rack).where(Rack.id == rid))).scalar_one_or_none()
    _require(rack is not None, "rack not found: " + str(rid))
    _require(dev.status == "in_stock", "device must be in_stock to mount (current: " + str(dev.status) + ")")
    size = _device_u_size(dev)
    available = rack.available_units if rack.available_units is not None else 0
    _require(size <= available, "rack capacity exceeded: need " + str(size) + "U, available " + str(available) + "U")
    old_status = dev.status
    dev.status = "mounted"
    dev.rack_id = rid
    rack.available_units = max(0, available - size)
    db.add(DeviceLifecycle(device_id=dev.id, action="mount", from_status=old_status,
                       to_status="mounted", operator=getattr(current_user, "username", "system"), remark=remark))
    AuditService.log(db, username=getattr(current_user, "username", "system"), action="mount", target_type="device",
                    target_id=str(dev.id), detail="mount device " + str(dev.name) + " to rack " + str(rack.code) + " (" + str(size) + "U)")
    await with_commit_retry(db.commit)
    return {"tool": "mount_device", "result": "mounted", "device_id": did, "rack_id": rid, "u_used": size, "available_units": rack.available_units}


async def _exec_unmount_device(db, args, current_user):
    from sqlalchemy import select
    from app.models import Device, Rack, DeviceLifecycle
    from app.db.retry import with_commit_retry
    from app.services.audit_service import AuditService
    did = int(args.get("device_id"))
    remark = args.get("remark")
    dev = (await db.execute(select(Device).where(Device.id == did))).scalar_one_or_none()
    _require(dev is not None, "device not found: " + str(did))
    _require(dev.status == "mounted", "device is not mounted (current: " + str(dev.status) + ")")
    rack = None
    if dev.rack_id is not None:
        rack = (await db.execute(select(Rack).where(Rack.id == dev.rack_id))).scalar_one_or_none()
    size = _device_u_size(dev)
    old_status = dev.status
    dev.status = "in_stock"
    if rack is not None:
        rack.available_units = min(rack.total_units or 0, (rack.available_units or 0) + size)
    rack_id = dev.rack_id
    dev.rack_id = None
    db.add(DeviceLifecycle(device_id=dev.id, action="unmount", from_status=old_status,
                       to_status="in_stock", operator=getattr(current_user, "username", "system"), remark=remark))
    AuditService.log(db, username=getattr(current_user, "username", "system"), action="unmount", target_type="device",
                    target_id=str(dev.id), detail="unmount device " + str(dev.name) + (" from rack " + str(rack.code) if rack else ""))
    await with_commit_retry(db.commit)
    return {"tool": "unmount_device", "result": "unmounted", "device_id": did, "rack_id": rack_id}


async def _exec_create_alert_rule(db, args, operator):
    from app.services.alert_service import AlertRuleService
    name = str(args.get("name") or "").strip()[:128]
    code = str(args.get("code") or "").strip()[:64]
    metric = str(args.get("metric") or "").strip()[:64]
    condition = str(args.get("condition") or "").strip()
    _require(bool(name), "name is required")
    _require(bool(code), "code is required")
    _require(bool(metric), "metric is required")
    _require(condition in _VALID_CONDITIONS, "invalid condition: " + str(condition))
    try:
        threshold = float(args.get("threshold"))
    except (TypeError, ValueError):
        raise ValueError("threshold must be a number")
    alert_level = str(args.get("alert_level") or "general")
    if alert_level not in _VALID_LEVELS:
        alert_level = "general"
    enabled = bool(args.get("enabled", True))
    notify = args.get("notify_methods")
    service = AlertRuleService(db)
    class Req:
        pass
    r = Req()
    r.name, r.code, r.metric = name, code, metric
    r.condition, r.threshold = condition, threshold
    r.alert_level, r.enabled, r.notify_methods = alert_level, enabled, notify
    try:
        obj = await service.create(r)
    except Exception as e:
        raise ValueError(str(e))
    return {"tool": "create_alert_rule", "result": "created", "rule_id": obj.id, "name": name, "metric": metric, "threshold": threshold}

async def _exec_create_work_order(db, args, operator):
    from sqlalchemy import select
    from app.models import User
    from app.api.v1.work_orders import generate_order_no
    from app.db.retry import with_commit_retry
    from app.db.compat_sql import exec_sql
    title = str(args.get("title") or "").strip()[:256]
    _require(bool(title), "title is required")
    description = str(args.get("description"))[:2000] if args.get("description") else None
    priority = args.get("priority") or "normal"
    if priority not in _VALID_PRIORITIES:
        priority = "normal"
    res = await db.execute(select(User).where(User.username == operator))
    user = res.scalar_one_or_none()
    _require(user is not None, "operator user not found")
    order_no = generate_order_no()
    await exec_sql(db,
        "INSERT INTO work_orders (order_no, title, description, priority, device_id, facility_id, status, creator_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (order_no, title, description, priority, args.get("device_id"), args.get("facility_id"), "pending", user.id))
    await with_commit_retry(db.commit)
    row = await exec_sql(db, "SELECT id FROM work_orders WHERE order_no = ?", (order_no,))
    order_id = row.fetchone().id
    return {"tool": "create_work_order", "result": "created", "order_id": order_id,
            "order_no": order_no, "title": title, "priority": priority}


async def _exec_handle_alert(db, args, operator):
    from app.services.alert_service import AlertService
    alert_id = int(args.get("alert_id"))
    action_type = args.get("action_type")
    if action_type not in _VALID_ALERT_ACTIONS:
        raise ValueError("invalid action_type: " + str(action_type))
    service = AlertService(db)
    alert = await service.handle(alert_id, {
        "action_type": action_type, "remark": args.get("remark"), "root_cause": args.get("root_cause")
    }, operator)
    if not alert:
        raise ValueError("alert " + str(alert_id) + " not found")
    return {"tool": "handle_alert", "result": "handled", "alert_id": alert_id, "status": alert.status}
