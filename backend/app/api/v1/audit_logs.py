"""审计日志API路由"""
import io
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user, require_permission
from app.models.user import User
from app.schemas.audit_log import (
    AuditLogResponse, AuditLogPageResponse, AuditSummaryResponse,
)
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["审计日志"])

ACTION_LABELS = {
    "login": "登录", "logout": "退出", "create": "创建", "update": "更新",
    "delete": "删除", "export": "导出", "mount": "上架", "unmount": "下架",
    "move": "挪位", "handle": "处理", "approve": "审批", "reject": "驳回",
    "assign": "分配", "start": "开始", "complete": "完成", "verify": "核验",
    "close": "关闭", "comment": "评论", "upload": "上传", "execute": "执行",
}


@router.get("", response_model=AuditLogPageResponse)
async def list_audit_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    action: Optional[str] = Query(None, description="操作类型"),
    target_type: Optional[str] = Query(None, description="对象类型"),
    username: Optional[str] = Query(None, description="操作用户"),
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("audit:view")),
):
    """获取审计日志列表（分页+多条件筛选）"""
    service = AuditService(db)
    logs, total = await service.get_audit_logs(
        page=page,
        page_size=page_size,
        keyword=keyword,
        action=action,
        target_type=target_type,
        username=username,
        start_date=start_date,
        end_date=end_date,
    )
    return AuditLogPageResponse(
        items=[AuditLogResponse.model_validate(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/summary", response_model=AuditSummaryResponse)
async def audit_summary(
    days: int = Query(7, ge=1, le=365, description="统计最近多少天"),
    start_date: Optional[datetime] = Query(None, description="开始时间(可选)"),
    end_date: Optional[datetime] = Query(None, description="结束时间(可选)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("audit:view")),
):
    """审计统计：总数/按操作类型/对象/用户/近 N 天趋势"""
    service = AuditService(db)
    return await service.summary(days=days, start_date=start_date, end_date=end_date)


@router.get("/export")
async def export_audit_logs(
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    action: Optional[str] = Query(None, description="操作类型"),
    target_type: Optional[str] = Query(None, description="对象类型"),
    username: Optional[str] = Query(None, description="操作用户"),
    start_date: Optional[datetime] = Query(None, description="开始时间"),
    end_date: Optional[datetime] = Query(None, description="结束时间"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("audit:view")),
):
    """导出符合条件的审计日志为 Excel(.xlsx)，预设列宽，时间列正常显示"""
    service = AuditService(db)
    logs = await service.export_all(
        keyword=keyword,
        action=action,
        target_type=target_type,
        username=username,
        start_date=start_date,
        end_date=end_date,
    )

    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "审计日志"

    headers = ["ID", "操作用户", "操作类型", "对象类型", "对象ID", "操作详情", "IP", "请求路径", "操作时间"]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="4472C4")
    for col in range(1, len(headers) + 1):
        c = ws.cell(row=1, column=col)
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center")

    for log in logs:
        ws.append([
            log.id,
            log.username,
            ACTION_LABELS.get(log.action, log.action),
            log.target_type,
            log.target_id or "",
            log.detail or "",
            log.ip_address or "",
            log.request_path or "",
            log.created_at if log.created_at else None,
        ])

    # 预设列宽，避免 Excel 打开时因列过窄显示星号/加载不全
    col_widths = {"A": 8, "B": 14, "C": 12, "D": 14, "E": 10, "F": 50, "G": 16, "H": 40, "I": 22}
    for col_letter, width in col_widths.items():
        ws.column_dimensions[col_letter].width = width

    # 时间列设置日期格式
    for row in ws.iter_rows(min_row=2, min_col=9, max_col=9):
        for cell in row:
            if cell.value is not None:
                cell.number_format = "YYYY-MM-DD HH:MM:SS"

    # 冻结表头
    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    data = buf.getvalue()
    filename = f"audit_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/retention")
async def cleanup_retention(
    days: int = Query(180, ge=7, le=3650, description="仅保留最近多少天，更早的将被清理"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """按保留策略清理历史审计日志（仅超级管理员）"""
    if not current_user.is_super_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="仅超级管理员可清理审计日志")
    before = datetime.utcnow() - timedelta(days=days)
    service = AuditService(db)
    removed = await service.purge(before)
    return {"removed": removed, "kept_days": days}


@router.get("/{log_id}", response_model=AuditLogResponse)
async def get_audit_log(
    log_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("audit:view")),
):
    """获取审计日志详情"""
    service = AuditService(db)
    log = await service.get_audit_log_by_id(log_id)
    if not log:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="审计日志不存在")
    return AuditLogResponse.model_validate(log)
