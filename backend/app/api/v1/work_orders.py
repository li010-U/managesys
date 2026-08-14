"""Work Order Management API"""
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Request, status as fastapi_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission
from app.db.retry import with_commit_retry
from app.db.compat_sql import exec_sql
from app.models import User
from app.services.file_service import file_service
from app.services.audit_service import AuditService

from app.api.v1.auto_rules import apply_auto_rules, resolve_auto_complete
from app.schemas.work_order import (
    WorkOrderCategoryCreate,
    WorkOrderCategoryUpdate,
    WorkOrderCreate,
    WorkOrderUpdate,
    WorkOrderAssign,
    WorkOrderProcess,
    WorkOrderVerify,
    WorkOrderClose,
    WorkOrderCommentCreate,
)

router = APIRouter(prefix="/work-orders", tags=["Work Order"])


def generate_order_no():
    return f"WO{datetime.now().strftime('%Y%m%d%H%M%S')}"


# ============ Work Order Categories ============
@router.get("/categories", summary="Get work order categories")
async def get_categories(db: AsyncSession = Depends(get_db), _current_user: User = Depends(require_permission("work:view"))):
    result = await exec_sql(db, "SELECT * FROM work_order_categories ORDER BY sort, id")
    return {"data": [dict(r._mapping) for r in result.fetchall()]}


@router.post("/categories", summary="Create category")
async def create_category(
    request: Request,
    data: WorkOrderCategoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:create"))
):
    name = data.name
    code = data.code
    icon = data.icon
    sort = data.sort
    need_approval = data.need_approval
    
    await exec_sql(db, 
        "INSERT INTO work_order_categories (name, code, icon, sort, need_approval) VALUES (?, ?, ?, ?, ?)",
        (name, code, icon, sort, need_approval)
    )
    await with_commit_retry(db.commit)
    
    result = await exec_sql(db, "SELECT * FROM work_order_categories WHERE code = ?", (code,))
    AuditService.log_request(db, request, current_user=current_user, action="create", target_type="work_order_category", target_id=None, detail='??????: ' + str(data.name))

    return {"data": dict(result.fetchone()._mapping)}


@router.put("/categories/{category_id}", summary="Update category")
async def update_category(
    request: Request,
    category_id: int,
    data: WorkOrderCategoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:edit"))
):
    row = (await exec_sql(db, "SELECT id FROM work_order_categories WHERE id = ?", (category_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Category not found")
    updates, params = [], []
    for key, value in data.model_dump(exclude_unset=True).items():
        updates.append(f"{key} = ?")
        params.append(value)
    params.append(category_id)
    await exec_sql(db, "UPDATE work_order_categories SET {} WHERE id = ?".format(", ".join(updates)), tuple(params))
    await with_commit_retry(db.commit)
    result = (await exec_sql(db, "SELECT * FROM work_order_categories WHERE id = ?", (category_id,))).fetchone()
    AuditService.log_request(db, request, current_user=current_user, action="update", target_type="work_order_category", target_id=str(category_id), detail='??????')

    return {"data": dict(result._mapping)}


@router.delete("/categories/{category_id}", summary="Delete category")
async def delete_category(
    request: Request,
    category_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:delete"))
):
    await exec_sql(db, "DELETE FROM work_order_categories WHERE id = ?", (category_id,))
    await with_commit_retry(db.commit)
    AuditService.log_request(db, request, current_user=current_user, action="delete", target_type="work_order_category", target_id=str(category_id), detail='??????')

    return {"message": "Category deleted"}


# ============ Work Orders ============
@router.get("", summary="Get work order list")
async def get_work_orders(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("work:view"))
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
        LEFT JOIN rooms f ON w.facility_id = f.id
        WHERE {where_clause}
        ORDER BY w.created_at DESC
        LIMIT {page_size} OFFSET {offset}
    """
    
    total_sql = f"SELECT COUNT(*) AS cnt FROM work_orders w WHERE {where_clause}"
    total = (await exec_sql(db, total_sql, tuple(params))).scalar() or 0

    result = await exec_sql(db, sql, tuple(params))
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
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/stats", summary="Get work order stats")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("work:view"))
):
    status_row = (await exec_sql(db, "SELECT status, COUNT(*) as cnt FROM work_orders GROUP BY status")).fetchall()
    counts = {row.status: row.cnt for row in status_row}
    total = sum(counts.values())
    pending = counts.get("pending", 0)
    processing = counts.get("assigned", 0) + counts.get("processing", 0)
    completed = counts.get("completed", 0)
    closed = counts.get("closed", 0)

    mine_row = (await exec_sql(db, "SELECT status, COUNT(*) as cnt FROM work_orders WHERE assignee_id = ? GROUP BY status", (current_user.id,))).fetchall()
    mine = {row.status: row.cnt for row in mine_row}
    my_pending = mine.get("assigned", 0)
    my_processing = mine.get("processing", 0)

    return {
        "data": {
            "total": total, "pending": pending, "processing": processing,
            "completed": completed, "closed": closed,
            "my_pending": my_pending, "my_processing": my_processing
        }
    }

# ============ Work Order Detail ============
@router.get("/{work_order_id}", summary="Get work order detail")
async def get_work_order(
    work_order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("work:view"))
):
    result = await exec_sql(db, """
        SELECT w.*, c.name as category_name,
               creator.username as creator_name,
               assignee.username as assignee_name,
               d.name as device_name,
               f.name as facility_name,
               u2.username as approver_name
        FROM work_orders w
        LEFT JOIN work_order_categories c ON w.category_id = c.id
        LEFT JOIN users creator ON w.creator_id = creator.id
        LEFT JOIN users assignee ON w.assignee_id = assignee.id
        LEFT JOIN devices d ON w.device_id = d.id
        LEFT JOIN rooms f ON w.facility_id = f.id
        LEFT JOIN users u2 ON w.approved_by = u2.id
        WHERE w.id = ?
    """, (work_order_id,))
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "Work order not found")

    attach_result = await exec_sql(db, """
        SELECT wa.*, u.username as uploader_name
        FROM work_order_attachments wa
        LEFT JOIN users u ON wa.uploader_id = u.id
        WHERE wa.work_order_id = ?
        ORDER BY wa.created_at DESC
    """, (work_order_id,))
    attachments = [dict(r._mapping) for r in attach_result.fetchall()]

    comment_result = await exec_sql(db, """
        SELECT wc.*, u.username as user_name
        FROM work_order_comments wc
        LEFT JOIN users u ON wc.user_id = u.id
        WHERE wc.work_order_id = ?
        ORDER BY wc.created_at
    """, (work_order_id,))
    comments = [dict(r._mapping) for r in comment_result.fetchall()]

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
            "comment_count": len(comments), "attachments": attachments,
            "need_approval": getattr(order, "need_approval", None),
            "approved_by": getattr(order, "approved_by", None),
            "approver_name": getattr(order, "approver_name", None),
            "approved_at": getattr(order, "approved_at", None),
            "reject_reason": getattr(order, "reject_reason", None),
        }
    }


@router.post("", summary="Create work order")
async def create_work_order(
    request: Request,
    data: WorkOrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:create"))
):
    order_no = generate_order_no()
    title = data.title
    description = data.description
    category_id = data.category_id
    priority = data.priority
    device_id = data.device_id
    facility_id = data.facility_id
    assignee_id = data.assignee_id
    plan_date = data.plan_date
    estimated_hours = data.estimated_hours

    status = "assigned" if assignee_id else "pending"

    priority, assignee_id, applied_rule = await apply_auto_rules(
        db, title, description, category_id, priority, assignee_id
    )
    if applied_rule and assignee_id:
        status = "assigned"

    # 若分类需要审批，则进入待审批状态
    need_approval = False
    if category_id:
        cat_row = (await exec_sql(db, "SELECT need_approval FROM work_order_categories WHERE id = ?", (category_id,))).fetchone()
        if cat_row and cat_row.need_approval:
            need_approval = True
            status = "awaiting_approval"
            assignee_id = None

    await exec_sql(db, """
        INSERT INTO work_orders (order_no, title, description, category_id, priority, device_id, facility_id, assignee_id, plan_date, estimated_hours, status, creator_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (order_no, title, description, category_id, priority, device_id, facility_id, assignee_id, plan_date, estimated_hours, status, current_user.id))
    await with_commit_retry(db.commit)

    result = await exec_sql(db, "SELECT id FROM work_orders WHERE order_no = ?", (order_no,))
    order_id = result.fetchone().id

    if applied_rule:
        await exec_sql(db, "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
            (order_id, current_user.id, "Auto rule applied: " + applied_rule, "process"))
        await with_commit_retry(db.commit)

    await resolve_auto_complete(db, order_id)

    AuditService.log_request(db, request, current_user=current_user, action="create", target_type="work_order", target_id=str(order_id), detail='????: ' + str(title))

    return await get_work_order(order_id, db, current_user)


@router.put("/{work_order_id}", summary="Update work order")
async def update_work_order(
    request: Request,
    work_order_id: int,
    data: WorkOrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:edit"))
):
    result = await exec_sql(db, "SELECT status FROM work_orders WHERE id = ?", (work_order_id,))
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "Work order not found")
    if order.status in ["completed", "closed"]:
        raise HTTPException(400, "Cannot update completed or closed work order")

    updates = []
    params = []
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            updates.append(f"{key} = ?")
            params.append(value)

    if updates:
        params.append(work_order_id)
        await exec_sql(db, f"UPDATE work_orders SET {', '.join(updates)} WHERE id = ?", tuple(params))
        await with_commit_retry(db.commit)

    AuditService.log_request(db, request, current_user=current_user, action="update", target_type="work_order", target_id=str(work_order_id), detail='????')

    return await get_work_order(work_order_id, db, current_user)


@router.post("/{work_order_id}/assign", summary="Assign work order")
async def assign_work_order(
    request: Request,
    work_order_id: int,
    data: WorkOrderAssign,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:edit"))
):
    assignee_id = data.assignee_id
    if not assignee_id:
        raise HTTPException(400, "Assignee is required")

    await exec_sql(db,
        "UPDATE work_orders SET assignee_id = ?, status = 'assigned' WHERE id = ?",
        (assignee_id, work_order_id)
    )
    await exec_sql(db,
        "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, "Work order assigned", "process")
    )
    await with_commit_retry(db.commit)

    AuditService.log_request(db, request, current_user=current_user, action="assign", target_type="work_order", target_id=str(work_order_id), detail='????: ' + str(assignee_id))

    return await get_work_order(work_order_id, db, current_user)


@router.post("/{work_order_id}/start", summary="Start work order")
async def start_work_order(
    request: Request,
    work_order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:edit"))
):
    row = (await exec_sql(db, "SELECT assignee_id, status FROM work_orders WHERE id = ?", (work_order_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Work order not found")
    if row.status not in {"assigned", "pending"}:
        raise HTTPException(400, "Cannot start work order in status '{0}'".format(row.status))
    if row.assignee_id is not None and row.assignee_id != current_user.id and not current_user.is_super_admin:
        raise HTTPException(403, "Only the assignee can start this work order")

    await exec_sql(db,
        "UPDATE work_orders SET status = 'processing', start_time = CURRENT_TIMESTAMP WHERE id = ?",
        (work_order_id,)
    )
    await exec_sql(db,
        "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, "Started processing", "process")
    )
    await with_commit_retry(db.commit)

    AuditService.log_request(db, request, current_user=current_user, action="start", target_type="work_order", target_id=str(work_order_id), detail='??????')

    return await get_work_order(work_order_id, db, current_user)


@router.post("/{work_order_id}/complete", summary="Complete work order")
async def complete_work_order(
    request: Request,
    work_order_id: int,
    data: WorkOrderProcess,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:edit"))
):
    result = data.result
    actual_hours = data.actual_hours

    row = (await exec_sql(db, "SELECT assignee_id, status FROM work_orders WHERE id = ?", (work_order_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Work order not found")
    if row.status != "processing":
        raise HTTPException(400, "Cannot complete work order in status '{0}'".format(row.status))
    if row.assignee_id is not None and row.assignee_id != current_user.id and not current_user.is_super_admin:
        raise HTTPException(403, "Only the assignee can complete this work order")

    await exec_sql(db, "UPDATE work_orders SET status = 'pending_verify', result = ?, end_time = CURRENT_TIMESTAMP, actual_hours = ? WHERE id = ?",
        (result, actual_hours or 0, work_order_id))
    await exec_sql(db,
        "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, "Completed: {0}".format(result), "verify")
    )
    await with_commit_retry(db.commit)

    AuditService.log_request(db, request, current_user=current_user, action="complete", target_type="work_order", target_id=str(work_order_id), detail='????')

    return await get_work_order(work_order_id, db, current_user)


@router.post("/{work_order_id}/verify", summary="Verify work order")
async def verify_work_order(
    request: Request,
    work_order_id: int,
    data: WorkOrderVerify,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:edit"))
):
    accept = data.accept
    satisfaction = data.satisfaction
    feedback = data.feedback

    row = (await exec_sql(db, "SELECT creator_id, status FROM work_orders WHERE id = ?", (work_order_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Work order not found")
    if row.status != "pending_verify":
        raise HTTPException(400, "Cannot verify work order in status '{0}'".format(row.status))
    if row.creator_id != current_user.id and not current_user.is_super_admin:
        raise HTTPException(403, "Only the creator can verify this work order")

    new_status = "completed" if accept else "processing"
    await exec_sql(db, "UPDATE work_orders SET status = ?, satisfaction = ?, feedback = ? WHERE id = ?",
        (new_status, satisfaction, feedback, work_order_id))

    content = "Verified and accepted" if accept else "Verification failed, needs rework"
    await exec_sql(db,
        "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, content, "verify")
    )
    await with_commit_retry(db.commit)

    AuditService.log_request(db, request, current_user=current_user, action="verify", target_type="work_order", target_id=str(work_order_id), detail='????')

    return await get_work_order(work_order_id, db, current_user)


@router.post("/{work_order_id}/close", summary="Close work order")
async def close_work_order(
    request: Request,
    work_order_id: int,
    data: WorkOrderClose,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:edit"))
):
    row = (await exec_sql(db, "SELECT creator_id, status FROM work_orders WHERE id = ?", (work_order_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Work order not found")
    if row.status != "completed":
        raise HTTPException(400, "Cannot close work order in status '{0}'".format(row.status))
    if row.creator_id != current_user.id and not current_user.is_super_admin:
        raise HTTPException(403, "Only the creator can close this work order")

    remark = data.remark or ""
    await exec_sql(db, "UPDATE work_orders SET status = 'closed' WHERE id = ?", (work_order_id,))
    await exec_sql(db,
        "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, "Closed: {0}".format(remark), "close")
    )
    await with_commit_retry(db.commit)

    AuditService.log_request(db, request, current_user=current_user, action="close", target_type="work_order", target_id=str(work_order_id), detail='????')

    return await get_work_order(work_order_id, db, current_user)


@router.post("/{work_order_id}/comments", summary="Add comment")
async def add_comment(
    request: Request,
    work_order_id: int,
    data: WorkOrderCommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:edit"))
):
    content = data.content
    comment_type = data.comment_type

    await exec_sql(db,
        "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, content, comment_type)
    )
    await with_commit_retry(db.commit)

    result = await exec_sql(db, "SELECT * FROM work_order_comments ORDER BY id DESC LIMIT 1")
    AuditService.log_request(db, request, current_user=current_user, action="comment", target_type="work_order", target_id=str(work_order_id), detail='??????')

    return {"data": dict(result.fetchone()._mapping)}


@router.post("/{work_order_id}/attachments", summary="Upload attachment")
async def upload_attachment(
    request: Request,
    work_order_id: int,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:edit"))
):
    order = (await exec_sql(db, "SELECT id FROM work_orders WHERE id = ?", (work_order_id,))).fetchone()
    if not order:
        raise HTTPException(404, "Work order not found")
    try:
        info = await file_service.save_upload(file, sub_dir="work_orders")
    except ValueError as e:
        raise HTTPException(status_code=fastapi_status.HTTP_400_BAD_REQUEST, detail=str(e))
    await exec_sql(db, """
        INSERT INTO work_order_attachments (work_order_id, file_name, file_path, file_size, file_type, uploader_id)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (work_order_id, info["original_name"], info["relative_path"], info["size"], info["mime_type"], current_user.id))
    await with_commit_retry(db.commit)
    result = (await exec_sql(db, """
        SELECT wa.*, u.username as uploader_name
        FROM work_order_attachments wa LEFT JOIN users u ON wa.uploader_id = u.id
        WHERE wa.work_order_id = ? ORDER BY wa.id DESC LIMIT 1
    """, (work_order_id,))).fetchone()
    AuditService.log_request(db, request, current_user=current_user, action="upload", target_type="work_order", target_id=str(work_order_id), detail='??????')

    return {"data": dict(result._mapping)}


@router.get("/attachments/{attachment_id}/download", summary="Download attachment")
async def download_attachment(
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("work:view"))
):
    from fastapi.responses import FileResponse
    row = (await exec_sql(db, "SELECT * FROM work_order_attachments WHERE id = ?", (attachment_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Attachment not found")
    file_path = file_service.get_file_path(row.file_path)
    if not file_path:
        raise HTTPException(404, "File not found")
    return FileResponse(str(file_path), filename=row.file_name, media_type="application/octet-stream")


@router.delete("/attachments/{attachment_id}", summary="Delete attachment")
async def delete_attachment(
    request: Request,
    attachment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:delete"))
):
    row = (await exec_sql(db, "SELECT * FROM work_order_attachments WHERE id = ?", (attachment_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Attachment not found")
    if row.uploader_id != current_user.id and not current_user.is_super_admin:
        raise HTTPException(403, "Only the uploader can delete this attachment")
    await exec_sql(db, "DELETE FROM work_order_attachments WHERE id = ?", (attachment_id,))
    await with_commit_retry(db.commit)
    file_service.delete_file(row.file_path)
    AuditService.log_request(db, request, current_user=current_user, action="delete", target_type="work_order", target_id=str(attachment_id), detail='??????')

    return {"message": "Attachment deleted"}



@router.post("/{work_order_id}/approve", summary="Approve work order")
async def approve_work_order(
    request: Request,
    work_order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:edit"))
):
    row = (await exec_sql(db, "SELECT status, assignee_id, title FROM work_orders WHERE id = ?", (work_order_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Work order not found")
    if row.status != "awaiting_approval":
        raise HTTPException(400, "Only work orders awaiting approval can be approved")
    new_status = "assigned" if row.assignee_id else "pending"
    await exec_sql(db, "UPDATE work_orders SET status = ?, approved_by = ?, approved_at = CURRENT_TIMESTAMP, reject_reason = NULL WHERE id = ?",
        (new_status, current_user.id, work_order_id))
    await exec_sql(db, "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, "Approved by " + current_user.username, "process"))
    await with_commit_retry(db.commit)
    AuditService.log_request(db, request, current_user=current_user, action="approve", target_type="work_order", target_id=str(work_order_id), detail='??????')

    return await get_work_order(work_order_id, db, current_user)


@router.post("/{work_order_id}/reject", summary="Reject work order")
async def reject_work_order(
    request: Request,
    work_order_id: int,
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:edit"))
):
    reason = (data or {}).get("reason") or ""
    row = (await exec_sql(db, "SELECT status FROM work_orders WHERE id = ?", (work_order_id,))).fetchone()
    if not row:
        raise HTTPException(404, "Work order not found")
    if row.status != "awaiting_approval":
        raise HTTPException(400, "Only work orders awaiting approval can be rejected")
    await exec_sql(db, "UPDATE work_orders SET status = 'closed', approved_by = ?, approved_at = CURRENT_TIMESTAMP, reject_reason = ? WHERE id = ?",
        (current_user.id, reason, work_order_id))
    await exec_sql(db, "INSERT INTO work_order_comments (work_order_id, user_id, content, comment_type) VALUES (?, ?, ?, ?)",
        (work_order_id, current_user.id, "Rejected: " + reason, "close"))
    await with_commit_retry(db.commit)
    AuditService.log_request(db, request, current_user=current_user, action="reject", target_type="work_order", target_id=str(work_order_id), detail='????')

    return await get_work_order(work_order_id, db, current_user)


@router.get("/users/list", summary="Get assignable users")
async def get_assignable_users(
    keyword: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("work:view"))
):
    if keyword:
        result = await exec_sql(db,
            "SELECT id, username, real_name, email FROM users WHERE is_active = ? AND (username LIKE ? OR real_name LIKE ?) ORDER BY id",
            (True, "%{0}%".format(keyword), "%{0}%".format(keyword))
        )
    else:
        result = await exec_sql(db,
            "SELECT id, username, real_name, email FROM users WHERE is_active = ? ORDER BY id",
            (True,)
        )
    users = [dict(r._mapping) for r in result.fetchall()]
    if not users:
        return {'data': []}
    ids = [u["id"] for u in users]
    placeholders = ",".join(["?"] * len(ids))
    workload_rows = (await exec_sql(db, """
        SELECT assignee_id, COUNT(*) AS active_cnt
        FROM work_orders
        WHERE assignee_id IN ({}) AND status IN ('assigned', 'processing')
        GROUP BY assignee_id
    """.format(placeholders), tuple(ids))).fetchall()
    workload = {row.assignee_id: row.active_cnt for row in workload_rows}
    for u in users:
        u["workload"] = workload.get(u["id"], 0)
    users.sort(key=lambda x: (x["workload"], x["id"]))
    return {'data': users, 'recommended_id': users[0]["id"] if users else None}


@router.delete("/{work_order_id}", summary="Delete work order")
async def delete_work_order(
    request: Request,
    work_order_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _ = Depends(require_permission("work:delete"))
):
    result = await exec_sql(db, "SELECT status, creator_id FROM work_orders WHERE id = ?", (work_order_id,))
    order = result.fetchone()
    if not order:
        raise HTTPException(404, "Work order not found")
    if order.creator_id != current_user.id and not current_user.is_super_admin:
        raise HTTPException(403, "Only creator can delete")
    if order.status not in ["pending", "closed"]:
        raise HTTPException(400, "Can only delete pending or closed work orders")

    await exec_sql(db, "DELETE FROM work_order_comments WHERE work_order_id = ?", (work_order_id,))
    await exec_sql(db, "DELETE FROM work_orders WHERE id = ?", (work_order_id,))
    await with_commit_retry(db.commit)
    AuditService.log_request(db, request, current_user=current_user, action="delete", target_type="work_order", target_id=str(work_order_id), detail='????')

    return {"message": "Deleted successfully"}
