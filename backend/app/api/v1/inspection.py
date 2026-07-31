"""Device Inspection API"""
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.core.deps import get_db, get_current_user
from app.models import User

router = APIRouter(prefix="/inspection", tags=["Device Inspection"])


def execute_sql(db, sql, params=None):
    """Execute SQL and return results"""
    if params:
        result = db.execute(sql, params)
    else:
        result = db.execute(sql)
    db.commit()
    return result


# ============ Inspection Templates ============
@router.get("/templates", summary="Get inspection templates")
async def get_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute("SELECT * FROM inspection_templates ORDER BY id")
    rows = result.fetchall()
    return {"data": [dict(r) for r in rows]}


@router.post("/templates", summary="Create inspection template")
async def create_template(
    template_in: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    name = template_in.get("name", "")
    desc = template_in.get("description", "")
    items = template_in.get("items")
    items_json = json.dumps(items) if items else None
    
    if items_json:
        sql = f"INSERT INTO inspection_templates (name, description, items) VALUES (?, ?, ?)"
        await db.execute(sql, (name, desc, items_json))
    else:
        sql = "INSERT INTO inspection_templates (name, description) VALUES (?, ?)"
        await db.execute(sql, (name, desc))
    await db.commit()
    
    result = await db.execute("SELECT * FROM inspection_templates WHERE name = ? ORDER BY id DESC LIMIT 1", (name,))
    return {"data": dict(result.fetchone())}


# ============ Inspection Plans ============
@router.get("/plans", summary="Get inspection plans")
async def get_plans(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    sql = """
        SELECT p.*, t.name as template_name, f.name as facility_name, u.username as assignee_name
        FROM inspection_plans p
        LEFT JOIN inspection_templates t ON p.template_id = t.id
        LEFT JOIN facilities f ON p.facility_id = f.id
        LEFT JOIN users u ON p.assignee_id = u.id
    """
    if status:
        sql += f" WHERE p.status = ?"
        result = await db.execute(sql + " ORDER BY p.created_at DESC", (status,))
    else:
        result = await db.execute(sql + " ORDER BY p.created_at DESC")
    
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
    plan_in: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    name = plan_in.get("name", "")
    desc = plan_in.get("description", "")
    plan_type = plan_in.get("plan_type", "periodic")
    frequency = plan_in.get("frequency", "daily")
    execute_time = plan_in.get("execute_time", "09:00")
    facility_id = plan_in.get("facility_id")
    template_id = plan_in.get("template_id")
    assignee_id = plan_in.get("assignee_id")
    
    sql = """INSERT INTO inspection_plans 
        (name, description, plan_type, frequency, execute_time, facility_id, template_id, assignee_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
    await db.execute(sql, (name, desc, plan_type, frequency, execute_time, facility_id, template_id, assignee_id))
    await db.commit()
    
    result = await db.execute("SELECT * FROM inspection_plans WHERE name = ? ORDER BY id DESC LIMIT 1", (name,))
    return {"data": dict(result.fetchone())}


@router.put("/plans/{plan_id}", summary="Update inspection plan")
async def update_plan(
    plan_id: int,
    plan_in: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    updates = []
    for key in ["name", "description", "frequency", "execute_time", "status"]:
        if key in plan_in and plan_in[key] is not None:
            updates.append(f"{key} = ?")
    
    if updates:
        values = [plan_in.get(k.replace("_", "")) or plan_in.get(k) for k in ["name", "description", "frequency", "execute_time", "status"]]
        values = [v for v in values if v is not None]
        values.append(plan_id)
        sql = f"UPDATE inspection_plans SET {', '.join(updates)} WHERE id = ?"
        await db.execute(sql, tuple(values))
        await db.commit()
    
    result = await db.execute("SELECT * FROM inspection_plans WHERE id = ?", (plan_id,))
    return {"data": dict(result.fetchone())}


@router.delete("/plans/{plan_id}", summary="Delete inspection plan")
async def delete_plan(
    plan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await db.execute("DELETE FROM inspection_plans WHERE id = ?", (plan_id,))
    await db.commit()
    return {"message": "Deleted successfully"}


# ============ Inspection Tasks ============
@router.get("/tasks", summary="Get inspection tasks")
async def get_tasks(
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    offset = (page - 1) * page_size
    sql = """
        SELECT t.*, u.username as assignee_name, f.name as facility_name
        FROM inspection_tasks t
        LEFT JOIN users u ON t.assignee_id = u.id
        LEFT JOIN facilities f ON t.facility_id = f.id
    """
    if status:
        sql += " WHERE t.status = ?"
        result = await db.execute(sql + f" ORDER BY t.scheduled_date DESC LIMIT {page_size} OFFSET {offset}", (status,))
    else:
        result = await db.execute(sql + f" ORDER BY t.scheduled_date DESC LIMIT {page_size} OFFSET {offset}")
    
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
    current_user: User = Depends(get_current_user)
):
    result = await db.execute("""
        SELECT t.*, u.username as assignee_name, f.name as facility_name
        FROM inspection_tasks t
        LEFT JOIN users u ON t.assignee_id = u.id
        LEFT JOIN facilities f ON t.facility_id = f.id
        WHERE t.id = ?
    """, (task_id,))
    task = result.fetchone()
    if not task:
        raise HTTPException(404, "Task not found")
    
    # Get records
    rec_result = await db.execute("""
        SELECT r.*, u.username as inspector_name, d.name as device_name
        FROM inspection_records r
        LEFT JOIN users u ON r.inspector_id = u.id
        LEFT JOIN devices d ON r.device_id = d.id
        WHERE r.task_id = ?
        ORDER BY r.checked_at
    """, (task_id,))
    records = [dict(r) for r in rec_result.fetchall()]
    
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
    current_user: User = Depends(get_current_user)
):
    # Get plan
    result = await db.execute("SELECT * FROM inspection_plans WHERE id = ?", (plan_id,))
    plan = result.fetchone()
    if not plan:
        raise HTTPException(404, "Plan not found")
    
    if not scheduled_date:
        scheduled_date = date.today().isoformat()
    
    # Create task
    await db.execute("""
        INSERT INTO inspection_tasks (plan_id, plan_name, facility_id, scheduled_date, assignee_id)
        VALUES (?, ?, ?, ?, ?)
    """, (plan_id, plan.name, plan.facility_id, scheduled_date, plan.assignee_id))
    await db.commit()
    
    result = await db.execute("SELECT * FROM inspection_tasks ORDER BY id DESC LIMIT 1")
    task = result.fetchone()
    
    # If has template, create records
    if plan.template_id:
        tpl_result = await db.execute("SELECT items FROM inspection_templates WHERE id = ?", (plan.template_id,))
        tpl = tpl_result.fetchone()
        if tpl and tpl.items:
            items = json.loads(tpl.items)
            for item in items:
                await db.execute("""
                    INSERT INTO inspection_records (task_id, item_name, item_key, check_content)
                    VALUES (?, ?, ?, ?)
                """, (task.id, item.get("name", ""), item.get("key", ""), item.get("content", "")))
            await db.execute("UPDATE inspection_tasks SET total_items = ? WHERE id = ?", (len(items), task.id))
            await db.commit()
    
    return await get_task(task.id, db, current_user)


@router.post("/tasks/{task_id}/start", summary="Start task")
async def start_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await db.execute("UPDATE inspection_tasks SET status = 'in_progress', start_time = datetime('now') WHERE id = ?", (task_id,))
    await db.commit()
    return await get_task(task_id, db, current_user)


@router.post("/tasks/{task_id}/complete", summary="Complete task")
async def complete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN check_result IS NOT NULL THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN check_result = 'abnormal' THEN 1 ELSE 0 END) as abnormal
        FROM inspection_records WHERE task_id = ?
    """, (task_id,))
    stats = result.fetchone()
    
    await db.execute("""
        UPDATE inspection_tasks 
        SET status = 'completed', end_time = datetime('now'),
            completed_items = ?, abnormal_items = ?
        WHERE id = ?
    """, (stats.completed or 0, stats.abnormal or 0, task_id))
    await db.commit()
    
    return await get_task(task_id, db, current_user)


# ============ Inspection Records ============
@router.post("/tasks/{task_id}/records", summary="Add inspection record")
async def add_record(
    task_id: int,
    record_in: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item_name = record_in.get("item_name", "")
    item_key = record_in.get("item_key", "")
    check_content = record_in.get("check_content", "")
    check_result = record_in.get("check_result", "normal")
    check_value = record_in.get("check_value", "")
    check_remark = record_in.get("check_remark", "")
    
    await db.execute("""
        INSERT INTO inspection_records (task_id, item_name, item_key, check_content, check_result, check_value, check_remark, inspector_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (task_id, item_name, item_key, check_content, check_result, check_value, check_remark, current_user.id))
    await db.commit()
    
    result = await db.execute("SELECT * FROM inspection_records ORDER BY id DESC LIMIT 1")
    return {"data": dict(result.fetchone())}


# ============ Inspection Issues ============
@router.get("/issues", summary="Get inspection issues")
async def get_issues(
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
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
        result = await db.execute(sql + " ORDER BY i.created_at DESC", (status,))
    else:
        result = await db.execute(sql + " ORDER BY i.created_at DESC")
    
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
    issue_in: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    issue_title = issue_in.get("issue_title", "")
    issue_desc = issue_in.get("issue_description", "")
    severity = issue_in.get("severity", "normal")
    record_id = issue_in.get("record_id")
    device_id = issue_in.get("device_id")
    
    await db.execute("""
        INSERT INTO inspection_issues (task_id, record_id, device_id, issue_title, issue_description, severity, reporter_id)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (task_id, record_id, device_id, issue_title, issue_desc, severity, current_user.id))
    await db.commit()
    
    result = await db.execute("SELECT * FROM inspection_issues ORDER BY id DESC LIMIT 1")
    return {"data": dict(result.fetchone())}


# ============ Stats ============
@router.get("/stats", summary="Get inspection stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    today = date.today().isoformat()
    
    result = await db.execute("SELECT COUNT(*) as cnt FROM inspection_plans WHERE status = 'active'")
    active_plan = result.fetchone().cnt
    
    result = await db.execute("SELECT COUNT(*) as cnt FROM inspection_plans")
    total_plan = result.fetchone().cnt
    
    result = await db.execute("SELECT COUNT(*) as cnt FROM inspection_tasks WHERE scheduled_date = ?", (today,))
    task_today = result.fetchone().cnt
    
    result = await db.execute("SELECT COUNT(*) as cnt FROM inspection_tasks WHERE scheduled_date < ? AND status != 'completed'", (today,))
    task_overdue = result.fetchone().cnt
    
    result = await db.execute("SELECT COUNT(*) as cnt FROM inspection_tasks WHERE status = 'completed'")
    task_completed = result.fetchone().cnt
    
    result = await db.execute("SELECT COUNT(*) as cnt FROM inspection_issues WHERE status IN ('open', 'in_progress')")
    issue_open = result.fetchone().cnt
    
    return {
        "data": {
            "plan_count": total_plan,
            "active_plan_count": active_plan,
            "task_today": task_today,
            "task_overdue": task_overdue,
            "task_completed": task_completed,
            "issue_open": issue_open,
            "issue_resolved": 0
        }
    }
