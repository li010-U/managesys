"""Work Order Management API"""
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models import User

router = APIRouter(prefix="/work-orders", tags=["Work Order"])


def generate_order_no():
    return f"WO{datetime.now().strftime('%Y%m%d%H%M%S')}"


# ============ Work Order Categories ============
@router.get("/categories", summary="Get work order categories")
async def get_categories(db: AsyncSession = Depends(get_db)):
    result = await db.execute("SELECT * FROM work_order_categories ORDER BY sort, id")
    return {"data": [dict(r) for r in result.fetchall()]}


@router.post("/categories", summary="Create category")
async def create_category(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    name = data.get("name", "")
    code = data.get("code", "")
    icon = data.get("icon", "")
    sort = data.get("sort", 0)
    
    await db.execute(
        "INSERT INTO work_order_categories (name, code, icon, sort) VALUES (?, ?, ?, ?)",
        (name, code, icon, sort)
    )
    await db.commit()
    
    result = await db.execute("SELECT * FROM work_order_categories WHERE code = ?", (code,))
    return {"data": dict(result.fetchone())}


# ============ Work Orders ============
@router.get("", summary="Get work order list")
async def get_work_orders(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    conditions = []
    params = []
    if status:
        conditions.append("w.status = ?")
        params.append(status)
    if priority:
        conditions.append("w.priority = ?")
        params.append(priority)
    if keyword:
        conditions.append("(w.title LIKE ? OR w.order_no LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%"])
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    offset = (page - 1) * page_size
    
    sql = f"""
        SELECT w.*, c.name as category_name,
               creator.username as creator_name,
               assignee.username as assignee_name,
               d.name as device_name,
               f.name as facility_name
        FROM work_orders w
        LEFT JOIN work_order_categories c ON w.category_id = c.id
        LEFT JOIN users creator ON w.creator_id = creator.id
        LEFT JOIN users assignee ON w.assignee_id = assignee.id
        LEFT JOIN devices d ON w.device_id = d.id
        LEFT JOIN facilities f ON w.facility_id = f.id
        WHERE {where_clause}
        ORDER BY w.created_at DESC
        LIMIT {page_size} OFFSET {offset}
    """
    
    result = await db.execute(sql, tuple(params))
    rows = result.fetchall()
    
    return {
        "data": [
            {
                "id": r.id, "order_no": r.order_no, "title": r.title,
                "category_name": r.category_name, "priority": r.priority, "status": r.status,
                "creator_id": r.creator_id, "creator_name": r.creator_name,
                "assignee_id": r.assignee_id, "assignee_name": r.assignee_name,
                "device_name": r.device_name, "facility_name": r.facility_name,
                "plan_date": r.plan_date, "created_at": r.created_at, "updated_at": r.updated_at
            }
            for r in rows
        ]
    }


@router.get("/stats", summary="Get work order stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute("SELECT COUNT(*) as cnt FROM work_orders")
    total = result.fetchone().cnt
    
    result = await db.execute("SELECT COUNT(*) as cnt FROM work_orders WHERE status = 'pending'")
    pending = result.fetchone().cnt
    
    result = await db.execute("SELECT COUNT(*) as cnt FROM work_orders WHERE status IN ('assigned', 'processing')")
    processing = result.fetchone().cnt
    
    result = await db.execute("SELECT COUNT(*) as cnt FROM work_orders WHERE status = 'completed'")
    completed = result.fetchone().cnt
    
    result = await db.execute("SELECT COUNT(*) as cnt FROM work_orders WHERE status = 'closed'")
    closed = result.fetchone().cnt
    
    result = await db.execute("SELECT COUNT(*) as cnt FROM work_orders WHERE assignee_id = ? AND status = 'assigned'", (current_user.id,))
    my_pending = result.fetchone().cnt
    
    return {
        "data": {
            "total": total, "pending": pending, "processing": processing,
            "completed": completed, "closed": closed,
            "my_pending": my_pending, "my_processing": 0
        }
    }


@router.get("/{work_order_id}", summary="Get work order detail")
async def get_work_order(
    work_order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute("""
        SELECT w.*, c.name as category_name,
               creator.username as creator_name,
               assignee.username as assignee_name,
               d.name as device_name,
               f.name as facility_name
        FROM work_orders w
        LEFT JOIN work_order_categories c ON w.category_id = c.id
        LEFT JOIN users creator ON w.creator_id = creator.id
        LEFT JOIN users assignee ON w.assignee_id = assignee.id
        LEFT JOIN devices d ON w.device_id = d.id
        LEFT JOIN facilities f ON w.facility_id = f.id
        WHERE w.id = ?
    """, (work_order_id,))
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "Work order not found")
    
    # Get comments
    comment_result = await db.execute("""
        SELECT wc.*, u.username as user_name
        FROM work_order_comments wc
        LEFT JOIN users u ON wc.user_id = u.id
        WHERE wc.work_order_id = ?
        ORDER BY wc.created_at
    """, (work_order_id,))
    comments = [dict(r) for r in comment_result.fetchall()]
    
    return {
        "data": {
            "id": order.id, "order_no": order.order_no, "title": order.title,
            "description": order.description, "category_id": order.category_id,
            "category_name": order.category_name, "priority": order.priority,
            "device_id": order.device_id, "device_name": order.device_name,
            "facility_id": order.facility_id, "facility_name": order.facility_name,
            "status": order.status, "creator_id": order.creator_id,
            "creator_name": order.creator_name, "assignee_id": order.assignee_id,
            "assignee_name": order.assignee_name, "plan_date": order.plan_date,
            "estimated_hours": order.estimated_hours, "start_time": order.start_time,
            "end_time": order.end_time, "actual_hours": order.actual_hours,
            "result": order.result, "satisfaction": order.satisfaction,
            "feedback": order.feedback, "created_at": order.created_at,
            "updated_at": order.updated_at, "comments": comments,
            "comment_count": len(comments), "attachments": []
        }
    }


@router.post("", summary="Create work order")
async def create_work_order(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    order_no = generate_order_no()
    title = data.get("title", "")
    description = data.get("description", "")
    category_id = data.get("category_id")
    priority = data.get("priority", "normal")
    device_id = data.get("device_id")
    facility_id = data.get("facility_id")
    assignee_id = data.get("assignee_id")
    plan_date = data.get("plan_date")
    estimated_hours = data.get("estimated_hours")
    
    status = "assigned" if assignee_id else "pending"
    
    await db.execute("""
        INSERT INTO work_orders (order_no, title, description, category_id, priority, device_id, facility_id, assignee_id, plan_date, estimated_hours, status, creator_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (order_no, title, description, category_id, priority, device_id, facility_id, assignee_id, plan_date, estimated_hours, status, current_user.id))
    await db.commit()
    
    result = await db.execute("SELECT id FROM work_orders WHERE order_no = ?", (order_no,))
    order_id = result.fetchone().id
    
    return await get_work_order(order_id, db, current_user)


@router.put("/{work_order_id}", summary="Update work order")
async def update_work_order(
    work_order_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute("SELECT status FROM work_orders WHERE id = ?", (work_order_id,))
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "Work order not found")
    if order.status in ["completed", "closed"]:
        raise HTTPException(400, "Cannot update completed or closed work order")
    
    updates = []
    params = []
    for key in ["title", "description", "priority", "plan_date", "estimated_hours"]:
        if key in data and data[key] is not None:
            updates.append(f"{key} = ?")
            params.append(data[key])
    
    if updates:
        params.append(work_order_id)
        await db.execute(f"UPDATE work_orders SET {', '.join(updates)} WHERE id = ?", tuple(params))
        await db.commit()
    
    return await get_work_order(work_order_id, db, current_user)


@router.post("/{work_order_id}/assign", summary="Assign work order")
async def assign_work_order(
    work_order_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    assignee_id = data.get("assignee_id")
    if not assignee_id:
        raise HTTPException(400, "Assignee is required")
    
    await db.execute(
        "UPDATE work_orders SET assignee_id = ?, status = 'assigned' WHERE id = ?",
        (assignee_id, work_order_id)
    )
    await db.commit()
    
    await db.execute(
        "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, "Work order assigned", "process")
    )
    await db.commit()
    
    return await get_work_order(work_order_id, db, current_user)


@router.post("/{work_order_id}/start", summary="Start work order")
async def start_work_order(
    work_order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await db.execute(
        "UPDATE work_orders SET status = 'processing', start_time = datetime('now') WHERE id = ?",
        (work_order_id,)
    )
    await db.commit()
    
    await db.execute(
        "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, "Started processing", "process")
    )
    await db.commit()
    
    return await get_work_order(work_order_id, db, current_user)


@router.post("/{work_order_id}/complete", summary="Complete work order")
async def complete_work_order(
    work_order_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = data.get("result", "")
    actual_hours = data.get("actual_hours")
    
    sql = "UPDATE work_orders SET status = 'pending_verify', result = ?, end_time = datetime('now') WHERE id = ?"
    await db.execute(sql, (result, work_order_id))
    if actual_hours:
        await db.execute("UPDATE work_orders SET actual_hours = ? WHERE id = ?", (actual_hours, work_order_id))
    await db.commit()
    
    await db.execute(
        "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, f"Completed: {result}", "verify")
    )
    await db.commit()
    
    return await get_work_order(work_order_id, db, current_user)


@router.post("/{work_order_id}/verify", summary="Verify work order")
async def verify_work_order(
    work_order_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    accept = data.get("accept", True)
    satisfaction = data.get("satisfaction", 5)
    feedback = data.get("feedback", "")
    
    new_status = "completed" if accept else "processing"
    
    await db.execute(
        "UPDATE work_orders SET status = ?, satisfaction = ?, feedback = ? WHERE id = ?",
        (new_status, satisfaction, feedback, work_order_id)
    )
    await db.commit()
    
    content = "Verified and accepted" if accept else "Verification failed, needs rework"
    await db.execute(
        "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, content, "verify")
    )
    await db.commit()
    
    return await get_work_order(work_order_id, db, current_user)


@router.post("/{work_order_id}/close", summary="Close work order")
async def close_work_order(
    work_order_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    await db.execute("UPDATE work_orders SET status = 'closed' WHERE id = ?", (work_order_id,))
    await db.commit()
    
    remark = data.get("remark", "")
    await db.execute(
        "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, f"Closed: {remark}", "close")
    )
    await db.commit()
    
    return await get_work_order(work_order_id, db, current_user)


@router.post("/{work_order_id}/comments", summary="Add comment")
async def add_comment(
    work_order_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    content = data.get("content", "")
    comment_type = data.get("comment_type", "normal")
    
    await db.execute(
        "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, content, comment_type)
    )
    await db.commit()
    
    result = await db.execute("SELECT * FROM work_order_comments ORDER BY id DESC LIMIT 1")
    return {"data": dict(result.fetchone())}


@router.get("/users/list", summary="Get assignable users")
async def get_assignable_users(
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if keyword:
        result = await db.execute(
            "SELECT id, username, real_name, email FROM users WHERE status = 'active' AND (username LIKE ? OR real_name LIKE ?) ORDER BY id",
            (f"%{keyword}%", f"%{keyword}%")
        )
    else:
        result = await db.execute(
            "SELECT id, username, real_name, email FROM users WHERE status = 'active' ORDER BY id"
        )
    return {'data': [dict(r) for r in result.fetchall()]}


@router.delete("/{work_order_id}", summary="Delete work order")
async def delete_work_order(
    work_order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute("SELECT status, creator_id FROM work_orders WHERE id = ?", (work_order_id,))
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "Work order not found")
    if order.creator_id != current_user.id:
        raise HTTPException(403, "Only creator can delete")
    if order.status not in ["pending", "closed"]:
        raise HTTPException(400, "Can only delete pending or closed work orders")
    
    await db.execute("DELETE FROM work_orders WHERE id = ?", (work_order_id,))
    await db.commit()
    return {"message": "Deleted successfully"}
