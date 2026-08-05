"""AI assistant write-tools: intent parsing + confirmed execution.

We do NOT let the LLM call write endpoints directly. Instead the
assistant (chat.py) parses the user request for a clearly expressed
write intent (create work order, handle an alert). If found, it emits a
TOOL_PROPOSAL event with a normalised argument set. The user must confirm
in the UI; confirmation calls POST /chat/tools/execute. The executor runs
the operation through the existing services. This keeps LLM output
non-authoritative for state changes.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

TOOLS: Dict[str, Dict[str, Any]] = {
    "create_work_order": {"name": "create_work_order", "action": "write",
        "description": "Create a new work order (title required).",
        "required": ["title"],
        "optional": ["description", "priority", "device_id", "facility_id"]},
    "handle_alert": {"name": "handle_alert", "action": "write",
        "description": "Handle an alert: acknowledge/resolve/ignore.",
        "required": ["alert_id", "action_type"],
        "optional": ["remark", "root_cause"]},
}

_VALID_ALERT_ACTIONS = {"acknowledge", "resolve", "ignore"}
_VALID_PRIORITIES = {"low", "normal", "high", "urgent"}


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
    if any(k in low for k in ["resolve", "resolved", "解决"]):
        return "resolve"
    if any(k in low for k in ["acknowledge", "accepted", "确认", "已知悉"]):
        return "acknowledge"
    if any(k in low for k in ["ignore", "忽略"]):
        return "ignore"
    return None


def parse_proposal(user_text: str, answer_text: str = "") -> Optional[Dict[str, Any]]:
    combined = "{0} {1}".format(user_text or "", answer_text or "").strip()
    if not combined:
        return None
    if re.search(r"(?:创建|新建|下单|open|create)\s*(?:一张|个)?\s*工单", combined, flags=re.IGNORECASE):
        title_m = re.search(r"标题\s*[:=]\s*(.+)", user_text or "")
        title = None
        if title_m:
            title = title_m.group(1).strip()
        if not title:
            first_line = next((ln for ln in (user_text or "").splitlines() if ln.strip()), "")
            title = re.sub(r"创建.*?工单", "", first_line).strip()
            title = (title or "工单")[:40]
        priority = "normal"
        if re.search(r"紧急|urgent", combined, flags=re.IGNORECASE):
            priority = "urgent"
        elif re.search(r"高|high", combined, flags=re.IGNORECASE):
            priority = "high"
        elif re.search(r"低|low", combined, flags=re.IGNORECASE):
            priority = "low"
        return {"tool": "create_work_order", "label": "create_work_order",
                "args": {"title": title, "description": None, "priority": priority,
                         "device_id": None, "facility_id": None}}
    action = _detect_action_type(combined)
    alert_id = _detect_alert_id(combined)
    if action and alert_id is not None:
        remark = None
        rm = re.search(r"(?:remark|备注)\s*[:=]\s*(.+)", combined)
        if rm:
            remark = rm.group(1).strip() or None
        return {"tool": "handle_alert", "label": "handle_alert",
                "args": {"alert_id": alert_id, "action_type": action,
                         "remark": remark, "root_cause": None}}
    return None


async def execute(db: AsyncSession, tool: str, args: Dict[str, Any], operator: str) -> Dict[str, Any]:
    if tool == "create_work_order":
        return await _exec_create_work_order(db, args, operator)
    if tool == "handle_alert":
        return await _exec_handle_alert(db, args, operator)
    raise ValueError("Unknown tool: " + str(tool))


async def _exec_create_work_order(db, args, operator):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models import User
    from app.api.v1.work_orders import generate_order_no
    from app.db.retry import with_commit_retry
    from app.db.compat_sql import exec_sql
    title = str(args.get("title") or "").strip()[:256]
    if not title:
        raise ValueError("title is required")
    description = str(args.get("description"))[:2000] if args.get("description") else None
    priority = args.get("priority") or "normal"
    if priority not in _VALID_PRIORITIES:
        priority = "normal"
    res = await db.execute(select(User).where(User.username == operator))
    user = res.scalar_one_or_none()
    if not user:
        raise ValueError("operator user not found")
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
