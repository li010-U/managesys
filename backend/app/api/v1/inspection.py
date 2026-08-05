"""Device Inspection API"""
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.core.deps import get_db, get_current_user, require_permission
from app.db.retry import with_commit_retry
from app.db.compat_sql import exec_sql
from app.models import User
from app.schemas.inspection import (
    InspectionTemplateCreate,
    InspectionPlanCreate,
    InspectionPlanUpdate,
    InspectionRecordCreate,
    InspectionIssueCreate,
)

router = APIRouter(prefix="/inspection", tags=["Device Inspection"])


# ============ Inspection Templates ============
@router.get("/templates", summary="Get inspection templates")
async def get_templates(db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("inspection:view"))
):
    result = await exec_sql(db, "SELECT * FROM inspection_templates ORDER BY id")
    rows = result.fetchall()
    return {"data": [dict(r._mapping) for r in rows]}


@router.post("/templates", summary="Create inspection template")
async def create_template(
    template_in: InspectionTemplateCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("inspection:create"))
):
    name = template_in.name
    desc = template_in.description
    items = template_in.items
    items_json = json.dumps(items) if items else None
    
    if items_json:
        sql = f"INSERT INTO inspection_templates (name, description, items) VALUES (?, ?, ?)"
        await exec_sql(db, sql, (name, desc, items_json))
    else:
        sql = "INSERT INTO inspection_templates (name, description) VALUES (?, ?)"
        await exec_sql(db, sql, (name, desc))
    await with_commit_retry(db.commit)
    
    result = await exec_sql(db, "SELECT * FROM inspection_templates WHERE name = ? ORDER BY id DESC LIMIT 1", (name,))
    return {"data": dict(result.fetchone()._mapping)}


# ============ Inspection Plans ============
@router.get("/plans", summary="Get inspection plans")
async def get_plans(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("inspection:view"))
):
    sql = """
        SELECT p.*, t.name as template_name, f.name as facility_name, u.username as assignee_name
        FROM inspection_plans p
        LEFT JOIN inspection_templates t ON p.template_id = t.id
        LEFT JOIN rooms f ON p.facility_id = f.id
        LEFT JOIN users u ON p.assignee_id = u.id
    """
    if status:
        sql += f" WHERE p.status = ?"
        result = await exec_sql(db, sql + " ORDER BY p.created_at DESC", (status,))
    else:
        result = await exec_sql(db, sql + " ORDER BY p.created_at DESC")
    
    rows = result.fetchall()
    return {
        "data": [
            {
                "id": r.id, "name": r.name, "plan_type": r.plan_type,
                "frequency": r.frequency, "status": r.status,
                "facility_name": r.facility_name, "template_name": r.template_name,
                "assignee_name": r.assignee_name, "next_execute_date": r.next_execute_date,
                "last_execute_date": r.last_execute_date, "created_at": r.created_at
            }
            for r in rows
        ]
    }


@router.post("/plans", summary="Create inspection plan")
async def create_plan(
    plan_in: InspectionPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("inspection:create"))
):
    name = plan_in.name
    desc = plan_in.description
    plan_type = plan_in.plan_type
    frequency = plan_in.frequency
    execute_time = plan_in.execute_time
    facility_id = plan_in.facility_id
    template_id = plan_in.template_id
    assignee_id = plan_in.assignee_id
    
    sql = """INSERT INTO inspection_plans 
        (name, description, plan_type, frequency, execute_time, facility_id, template_id, assignee_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
    await exec_sql(db, sql, (name, desc, plan_type, frequency, execute_time, facility_id, template_id, assignee_id))
    await with_commit_retry(db.commit)
    
    result = await exec_sql(db, "SELECT * FROM inspection_plans WHERE name = ? ORDER BY id DESC LIMIT 1", (name,))
    return {"data": dict(result.fetchone()._mapping)}


@router.put("/plans/{plan_id}", summary="Update inspection plan")
async def update_plan(
    plan_id: int,
    plan_in: InspectionPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("inspection:edit"))
):
    updates = []
    values = []
    for key, value in plan_in.model_dump(exclude_unset=True).items():
        if value is not None:
            updates.append(f"{key} = ?")
            values.append(value)

    if updates:
        values.append(plan_id)
        sql = f"UPDATE inspection_plans SET {', '.join(updates)} WHERE id = ?"
        await exec_sql(db, sql, tuple(values))
        await with_commit_retry(db.commit)
    
    result = await exec_sql(db, "SELECT * FROM inspection_plans WHERE id = ?", (plan_id,))
    return {"data": dict(result.fetchone()._mapping)}


@router.delete("/plans/{plan_id}", summary="Delete inspection plan")
async def delete_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("inspection:delete"))
):
    await exec_sql(db, "DELETE FROM inspection_plans WHERE id = ?", (plan_id,))
    await with_commit_retry(db.commit)
    return {"message": "Deleted successfully"}


# ============ Inspection Tasks ============
@router.get("/tasks", summary="Get inspection tasks")
async def get_tasks(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("inspection:view"))
):
    offset = (page - 1) * page_size
    sql = """
        SELECT t.*, u.username as assignee_name, f.name as facility_name
        FROM inspection_tasks t
        LEFT JOIN users u ON t.assignee_id = u.id
        LEFT JOIN rooms f ON t.facility_id = f.id
    """
    if status:
        sql += " WHERE t.status = ?"
        result = await exec_sql(db, sql + f" ORDER BY t.scheduled_date DESC LIMIT {page_size} OFFSET {offset}", (status,))
    else:
        result = await exec_sql(db, sql + f" ORDER BY t.scheduled_date DESC LIMIT {page_size} OFFSET {offset}")
    
    rows = result.fetchall()
    return {
        "data": [
            {
                "id": r.id, "plan_id": r.plan_id, "plan_name": r.plan_name,
                "status": r.status, "priority": r.priority,
                "assignee_name": r.assignee_name, "facility_name": r.facility_name,
                "scheduled_date": r.scheduled_date, "start_time": r.start_time,
                "end_time": r.end_time, "total_items": r.total_items,
                "completed_items": r.completed_items, "abnormal_items": r.abnormal_items,
                "created_at": r.created_at
            }
            for r in rows
        ]
    }


@router.get("/tasks/{task_id}", summary="Get task detail")
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("inspection:view"))
):
    result = await exec_sql(db, """
        SELECT t.*, u.username as assignee_name, f.name as facility_name
        FROM inspection_tasks t
        LEFT JOIN users u ON t.assignee_id = u.id
        LEFT JOIN rooms f ON t.facility_id = f.id
        WHERE t.id = ?
    """, (task_id,))
    task = result.fetchone()
    if not task:
        raise HTTPException(404, "Task not found")
    
    # Get records
    rec_result = await exec_sql(db, """
        SELECT r.*, u.username as inspector_name, d.name as device_name
        FROM inspection_records r
        LEFT JOIN users u ON r.inspector_id = u.id
        LEFT JOIN devices d ON r.device_id = d.id
        WHERE r.task_id = ?
        ORDER BY r.checked_at
    """, (task_id,))
    records = [dict(r._mapping) for r in rec_result.fetchall()]
    
    return {
        "data": {
            "id": task.id, "plan_id": task.plan_id, "plan_name": task.plan_name,
            "status": task.status, "priority": task.priority,
            "assignee_name": task.assignee_name, "facility_name": task.facility_name,
            "scheduled_date": task.scheduled_date, "start_time": task.start_time,
            "end_time": task.end_time, "total_items": task.total_items,
            "completed_items": task.completed_items, "abnormal_items": task.abnormal_items,
            "created_at": task.created_at, "records": records
        }
    }


@router.post("/tasks", summary="Create inspection task")
async def create_task(
    plan_id: int,
    scheduled_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("inspection:create"))
):
    # Get plan
    result = await exec_sql(db, "SELECT * FROM inspection_plans WHERE id = ?", (plan_id,))
    plan = result.fetchone()
    if not plan:
        raise HTTPException(404, "Plan not found")
    
    if not scheduled_date:
        scheduled_date = date.today().isoformat()
    
    # Create task
    await exec_sql(db, """
        INSERT INTO inspection_tasks (plan_id, plan_name, facility_id, scheduled_date, assignee_id)
        VALUES (?, ?, ?, ?, ?)
    """, (plan_id, plan.name, plan.facility_id, scheduled_date, plan.assignee_id))
    
    result = await exec_sql(db, "SELECT * FROM inspection_tasks ORDER BY id DESC LIMIT 1")
    task = result.fetchone()
    
    # If has template, create records
    if plan.template_id:
        tpl_result = await exec_sql(db, "SELECT items FROM inspection_templates WHERE id = ?", (plan.template_id,))
        tpl = tpl_result.fetchone()
        if tpl and tpl.items:
            items = json.loads(tpl.items)
            for item in items:
                await exec_sql(db, """
                    INSERT INTO inspection_records (task_id, item_name, item_key, check_content)
                    VALUES (?, ?, ?, ?)
                """, (task.id, item.get("name", ""), item.get("key", ""), item.get("content", "")))
            await exec_sql(db, "UPDATE inspection_tasks SET total_items = ? WHERE id = ?", (len(items), task.id))
    
    await with_commit_retry(db.commit)

    return await get_task(task.id, db, current_user)


@router.post("/tasks/{task_id}/start", summary="Start task")
async def start_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("inspection:edit"))
):
    task_row = (await exec_sql(db, "SELECT assignee_id, status FROM inspection_tasks WHERE id = ?", (task_id,))).fetchone()
    if not task_row:
        raise HTTPException(404, "Task not found")
    if task_row.status != "pending":
        raise HTTPException(400, "Cannot start task in status '{0}'".format(task_row.status))
    if task_row.assignee_id is not None and task_row.assignee_id != current_user.id and not current_user.is_super_admin:
        raise HTTPException(403, "Only the assignee can manage this task")
    await exec_sql(db, "UPDATE inspection_tasks SET status = 'in_progress', start_time = CURRENT_TIMESTAMP WHERE id = ?", (task_id,))
    await with_commit_retry(db.commit)
    return await get_task(task_id, db, current_user)


@router.post("/tasks/{task_id}/complete", summary="Complete task")
async def complete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("inspection:edit"))
):
    task_row = (await exec_sql(db, "SELECT assignee_id, status FROM inspection_tasks WHERE id = ?", (task_id,))).fetchone()
    if not task_row:
        raise HTTPException(404, "Task not found")
    if task_row.status not in {"in_progress", "pending"}:
        raise HTTPException(400, "Cannot complete task in status '{0}'".format(task_row.status))
    if task_row.assignee_id is not None and task_row.assignee_id != current_user.id and not current_user.is_super_admin:
        raise HTTPException(403, "Only the assignee can manage this task")
    result = await exec_sql(db, """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN check_result IS NOT NULL THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN check_result = 'abnormal' THEN 1 ELSE 0 END) as abnormal
        FROM inspection_records WHERE task_id = ?
    """, (task_id,))
    stats = result.fetchone()
    
    await exec_sql(db, """
        UPDATE inspection_tasks 
        SET status = 'completed', end_time = CURRENT_TIMESTAMP,
            completed_items = ?, abnormal_items = ?
        WHERE id = ?
    """, (stats.completed or 0, stats.abnormal or 0, task_id))
    await with_commit_retry(db.commit)
    
    return await get_task(task_id, db, current_user)


# ============ Inspection Records ============
@router.post("/tasks/{task_id}/records", summary="Add inspection record")
async def add_record(
    task_id: int,
    record_in: InspectionRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("inspection:edit"))
):
    item_name = record_in.item_name
    item_key = record_in.item_key
    check_content = record_in.check_content
    check_result = record_in.check_result
    check_value = record_in.check_value or ""
    check_remark = record_in.check_remark or ""
    
    await exec_sql(db, """
        INSERT INTO inspection_records (task_id, item_name, item_key, check_content, check_result, check_value, check_remark, inspector_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (task_id, item_name, item_key, check_content, check_result, check_value, check_remark, current_user.id))
    await with_commit_retry(db.commit)
    
    result = await exec_sql(db, "SELECT * FROM inspection_records ORDER BY id DESC LIMIT 1")
    return {"data": dict(result.fetchone()._mapping)}


# ============ Inspection Issues ============
@router.get("/issues", summary="Get inspection issues")
async def get_issues(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("inspection:view"))
):
    sql = """
        SELECT i.*, t.plan_name as task_name, d.name as device_name,
               r.username as reporter_name, h.username as handler_name
        FROM inspection_issues i
        LEFT JOIN inspection_tasks t ON i.task_id = t.id
        LEFT JOIN devices d ON i.device_id = d.id
        LEFT JOIN users r ON i.reporter_id = r.id
        LEFT JOIN users h ON i.handler_id = h.id
    """
    if status:
        sql += " WHERE i.status = ?"
        result = await exec_sql(db, sql + " ORDER BY i.created_at DESC", (status,))
    else:
        result = await exec_sql(db, sql + " ORDER BY i.created_at DESC")
    
    rows = result.fetchall()
    return {
        "data": [
            {
                "id": r.id, "task_id": r.task_id, "task_name": r.task_name,
                "device_name": r.device_name, "issue_title": r.issue_title,
                "severity": r.severity, "status": r.status,
                "reporter_name": r.reporter_name, "handler_name": r.handler_name,
                "created_at": r.created_at
            }
            for r in rows
        ]
    }


@router.post("/issues", summary="Create inspection issue")
async def create_issue(
    task_id: int,
    issue_in: InspectionIssueCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("inspection:create"))
):
    issue_title = issue_in.issue_title
    issue_desc = issue_in.issue_description
    severity = issue_in.severity
    record_id = issue_in.record_id
    device_id = issue_in.device_id
    
    await exec_sql(db, """
        INSERT INTO inspection_issues (task_id, record_id, device_id, issue_title, issue_description, severity, reporter_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (task_id, record_id, device_id, issue_title, issue_desc, severity, current_user.id))
    await with_commit_retry(db.commit)
    
    result = await exec_sql(db, "SELECT * FROM inspection_issues ORDER BY id DESC LIMIT 1")
    return {"data": dict(result.fetchone()._mapping)}


# ============ Stats ============
@router.get("/stats", summary="Get inspection stats")
async def get_stats(db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("inspection:view"))
):
    today = date.today().isoformat()

    plan_row = (await exec_sql(db, "SELECT COUNT(*) AS total, SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_cnt FROM inspection_plans")).fetchone()
    total_plan = plan_row.total or 0
    active_plan = plan_row.active_cnt or 0

    task_row = (await exec_sql(db, "SELECT SUM(CASE WHEN scheduled_date = ? THEN 1 ELSE 0 END) AS today_cnt, SUM(CASE WHEN scheduled_date < ? AND status != 'completed' THEN 1 ELSE 0 END) AS overdue_cnt, SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed_cnt FROM inspection_tasks", (today, today))).fetchone()
    task_today = task_row.today_cnt or 0
    task_overdue = task_row.overdue_cnt or 0
    task_completed = task_row.completed_cnt or 0

    issue_row = (await exec_sql(db, "SELECT SUM(CASE WHEN status IN ('open', 'in_progress') THEN 1 ELSE 0 END) AS open_cnt, SUM(CASE WHEN status IN ('resolved', 'closed') THEN 1 ELSE 0 END) AS resolved_cnt FROM inspection_issues")).fetchone()
    issue_open = issue_row.open_cnt or 0
    issue_resolved = issue_row.resolved_cnt or 0

    return {
        "data": {
            "plan_count": total_plan,
            "active_plan_count": active_plan,
            "task_today": task_today,
            "task_overdue": task_overdue,
            "task_completed": task_completed,
            "issue_open": issue_open,
            "issue_resolved": issue_resolved
        }
    }
