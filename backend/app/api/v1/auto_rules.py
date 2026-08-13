"""??????? API"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission
from app.db.retry import with_commit_retry
from app.db.compat_sql import exec_sql
from app.models import User

router = APIRouter(prefix="/work-order-rules", tags=["Work Order Auto Rules"])


class AutoRuleCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    enabled: bool = Field(True)
    match_keyword: Optional[str] = Field(None, max_length=256)
    match_category_id: Optional[int] = None
    match_priority: Optional[str] = None
    action_set_priority: Optional[str] = None
    action_assign_user_id: Optional[int] = None
    action_auto_complete: bool = Field(False)
    sort: int = Field(0)


class AutoRuleUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    enabled: Optional[bool] = None
    match_keyword: Optional[str] = Field(None, max_length=256)
    match_category_id: Optional[int] = None
    match_priority: Optional[str] = None
    action_set_priority: Optional[str] = None
    action_assign_user_id: Optional[int] = None
    action_auto_complete: Optional[bool] = None
    sort: Optional[int] = None


@router.get("", summary="List auto rules")
async def list_rules(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("work:view")),
):
    rows = (await exec_sql(db, """
        SELECT r.*, c.name as category_name, u.username as assign_username
        FROM work_order_auto_rules r
        LEFT JOIN work_order_categories c ON r.match_category_id = c.id
        LEFT JOIN users u ON r.action_assign_user_id = u.id
        ORDER BY r.sort ASC, r.id ASC
    """)).fetchall()
    return {"data": [dict(r._mapping) for r in rows]}


@router.post("", summary="Create auto rule")
async def create_rule(
    data: AutoRuleCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:edit")),
):
    await exec_sql(db, """
        INSERT INTO work_order_auto_rules
            (name, enabled, match_keyword, match_category_id, match_priority,
             action_set_priority, action_assign_user_id, action_auto_complete, sort, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (data.name, data.enabled, data.match_keyword, data.match_category_id, data.match_priority,
          data.action_set_priority, data.action_assign_user_id, data.action_auto_complete, data.sort, current_user.id))
    await with_commit_retry(db.commit)
    row = (await exec_sql(db, "SELECT * FROM work_order_auto_rules ORDER BY id DESC LIMIT 1")).fetchone()
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="create", target_type="auto_rule", target_id=str(row.id), detail=f"创建自动规则: {data.name}")
    return {"data": dict(row._mapping)}


@router.put("/{rule_id}", summary="Update auto rule")
async def update_rule(
    rule_id: int,
    data: AutoRuleUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("work:edit")),
):
    row = (await exec_sql(db, "SELECT id FROM work_order_auto_rules WHERE id = ?", (rule_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Rule not found")
    updates, params = [], []
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "match_keyword" and value is not None:
            value = value.strip()
        updates.append(f"{key} = ?")
        params.append(value)
    params.append(rule_id)
    await exec_sql(db, "UPDATE work_order_auto_rules SET {} WHERE id = ?".format(", ".join(updates)), tuple(params))
    await with_commit_retry(db.commit)
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="update", target_type="auto_rule", target_id=str(rule_id), detail=f"更新自动规则: {data.name or rule_id}")
    return {"message": "Rule updated"}


@router.delete("/{rule_id}", summary="Delete auto rule")
async def delete_rule(
    rule_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("work:delete")),
):
    await exec_sql(db, "DELETE FROM work_order_auto_rules WHERE id = ?", (rule_id,))
    await with_commit_retry(db.commit)
    from app.services.audit_service import AuditService
    AuditService.log_request(db, request, current_user=current_user, action="delete", target_type="auto_rule", target_id=str(rule_id), detail="删除自动规则")
    return {"message": "Rule deleted"}


# ============ ??????? ============
async def apply_auto_rules(db, title: str, description: Optional[str], category_id: Optional[int],
                           priority: str, assignee_id: Optional[int]):
    """?????????????/?????? (priority, assignee_id, applied_name)"""
    if assignee_id:
        return priority, assignee_id, None
    rows = (await exec_sql(db, """
        SELECT * FROM work_order_auto_rules WHERE enabled = ?
        ORDER BY sort ASC, id ASC
    """, (True,))).fetchall()
    if not rows:
        return priority, None, None
    haystack = "{} {}".format(title or "", description or "").lower()
    for r in rows:
        if r.match_keyword and r.match_keyword.strip():
            if r.match_keyword.strip().lower() not in haystack:
                continue
        if r.match_category_id and category_id and r.match_category_id != category_id:
            continue
        if r.match_priority and priority and r.match_priority != priority:
            continue
        new_priority = r.action_set_priority or priority
        new_assignee = r.action_assign_user_id
        return new_priority, new_assignee, r.name
    return priority, None, None


async def resolve_auto_complete(db, order_id: int):
    """???????????????? completed?????????"""
    order = (await exec_sql(db, "SELECT * FROM work_orders WHERE id = ?", (order_id,))).fetchone()
    if not order:
        return
    if order.status != "assigned":
        return
    # ?????????????????????
    rows = (await exec_sql(db, "SELECT * FROM work_order_auto_rules WHERE enabled = ? AND action_auto_complete = ? ORDER BY sort ASC, id ASC", (True, True))).fetchall()
    if not rows:
        return
    haystack = "{} {}".format(order.title or "", order.description or "").lower()
    for r in rows:
        if r.match_keyword and r.match_keyword.strip() and r.match_keyword.strip().lower() not in haystack:
            continue
        if r.match_category_id and order.category_id and r.match_category_id != order.category_id:
            continue
        if r.match_priority and order.priority and r.match_priority != order.priority:
            continue
        await exec_sql(db, """
            UPDATE work_orders SET status = 'completed', end_time = CURRENT_TIMESTAMP WHERE id = ?
        """, (order_id,))
        await exec_sql(db, """
            INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type)
            VALUES (?, ?, ?, ?)
        """, (order_id, order.assignee_id or order.creator_id, "?????????????", "process"))
        await with_commit_retry(db.commit)
        return
