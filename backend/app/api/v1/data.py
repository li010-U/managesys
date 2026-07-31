"""Data Import/Export API"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession
import csv
import io
from datetime import datetime

from app.core.deps import get_db, get_current_user
from app.models.user import User

router = APIRouter(prefix="/data", tags=["Data Import/Export"])

@router.get("/work-orders/export")
async def export_work_orders(
    status: str = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    where = "w.status = ?" if status else "1=1"
    params = [status] if status else []
    
    sql = """
        SELECT w.order_no, w.title, w.description, c.name as category,
               w.priority, w.status, w.plan_date,
               creator.username as creator, assignee.username as assignee,
               w.estimated_hours, w.actual_hours, w.created_at
        FROM work_orders w
        LEFT JOIN work_order_categories c ON w.category_id = c.id
        LEFT JOIN users creator ON w.creator_id = creator.id
        LEFT JOIN users assignee ON w.assignee_id = assignee.id
        WHERE {}
        ORDER BY w.created_at DESC
    """.format(where)
    
    result = await db.execute(sql, tuple(params))
    rows = result.fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Order No", "Title", "Description", "Category", "Priority", "Status", 
                     "Plan Date", "Creator", "Assignee", "Est. Hours", "Actual Hours", "Created At"])
    
    for r in rows:
        writer.writerow([r.order_no, r.title, r.description or "", r.category or "",
                        r.priority, r.status, r.plan_date or "",
                        r.creator or "", r.assignee or "",
                        r.estimated_hours or "", r.actual_hours or "", str(r.created_at)])
    
    filename = "work_orders_{}.csv".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
    return {"data": output.getvalue(), "filename": filename, "count": len(rows)}

@router.post("/work-orders/import")
async def import_work_orders(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "Only CSV files supported")
    
    content = await file.read()
    text = content.decode("utf-8-sig")
    
    reader = csv.DictReader(io.StringIO(text))
    
    cat_result = await db.execute("SELECT name, id FROM work_order_categories")
    categories = {r.name: r.id for r in cat_result.fetchall()}
    
    imported = 0
    errors = []
    
    for i, row in enumerate(reader):
        try:
            order_no = "WO{}{:03d}".format(datetime.now().strftime("%Y%m%d%H%M%S"), imported)
            title = row.get("Title", row.get("标题", ""))
            cat_name = row.get("Category", row.get("分类", ""))
            priority = row.get("Priority", "normal")
            
            await db.execute(
                "INSERT INTO work_orders (order_no, title, category_id, priority, status, creator_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, datetime(), datetime())",
                (order_no, title, categories.get(cat_name), priority, "pending", current_user.id)
            )
            imported += 1
        except Exception as e:
            errors.append("Row {}: {}".format(i+2, str(e)))
    
    await db.commit()
    return {"imported": imported, "errors": errors[:10]}

@router.get("/devices/export")
async def export_devices(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    sql = """
        SELECT d.name, d.asset_number, d.serial_number, d.brand, d.model,
               dt.name as device_type, d.management_ip, d.status
        FROM devices d
        LEFT JOIN device_types dt ON d.device_type_id = dt.id
        ORDER BY d.name
    """
    
    result = await db.execute(sql)
    rows = result.fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Name", "Asset Number", "Serial Number", "Brand", "Model", "Device Type", "Management IP", "Status"])
    
    for r in rows:
        writer.writerow([r.name, r.asset_number or "", r.serial_number or "", r.brand or "", r.model or "", r.device_type or "", r.management_ip or "", r.status])
    
    filename = "devices_{}.csv".format(datetime.now().strftime("%Y%m%d_%H%M%S"))
    return {"data": output.getvalue(), "filename": filename, "count": len(rows)}

@router.get("/statistics/overview")
async def get_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stats = {}
    for tbl in ["work_orders", "devices", "alerts", "users"]:
        result = await db.execute("SELECT COUNT(*) FROM {}".format(tbl))
        stats["{}_count".format(tbl)] = result.fetchone()[0]
    
    result = await db.execute("SELECT COUNT(*) FROM alerts WHERE status = ?", ("active",))
    stats["active_alerts"] = result.fetchone()[0]
    
    return {"data": stats}

@router.post("/work-orders/batch-assign")
async def batch_assign(
    data: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    ids = data.get("ids", [])
    assignee_id = data.get("assignee_id")
    
    if not ids or not assignee_id:
        raise HTTPException(400, "Missing parameters")
    
    count = 0
    for order_id in ids:
        result = await db.execute(
            "UPDATE work_orders SET assignee_id = ?, status = ? WHERE id = ?",
            (assignee_id, "assigned", order_id)
        )
        count += 1
    
    await db.commit()
    return {"message": "Assigned {} orders".format(count), "count": count}
