# -*- coding: utf-8 -*-
"""工作台 - 最近活动合并接口"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_permission
from app.models.user import User
from app.models.audit_log import AuditLog
from app.models.work_order import WorkOrder
from app.models.alert import Alert

router = APIRouter(prefix="/dashboard", tags=["工作台"])

ACTION_LABEL = {"login":"登录","logout":"退出","create":"创建","update":"更新","delete":"删除","export":"导出"}
TARGET_LABEL = {"user":"用户","role":"角色","device":"设备","room":"机房","rack":"机柜","system":"系统","alert":"告警","data_center":"数据中心","device_type":"设备类型","sensor":"传感器","message":"消息"}

def fmt_time(dt: datetime) -> str:
    if not dt:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M")

class ActivityItem(BaseModel):
    type: str
    text: str
    time: str
    color: str

@router.get("/activities", response_model=List[ActivityItem])
async def recent_activities(
    limit: int = Query(12, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_permission("monitor:view_dashboard")),
):
    items: list[tuple[datetime, ActivityItem]] = []

    # 1) 审计/操作日志
    audits = (await db.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)
    )).scalars().all()
    for a in audits:
        act = ACTION_LABEL.get(a.action, a.action)
        tgt = TARGET_LABEL.get(a.target_type, a.target_type)
        text = f"{a.username} {act}{tgt}"
        if a.detail:
            d = a.detail[0:60]
            text += f"：{d}"
        items.append((a.created_at, ActivityItem(type="audit", text=text, time=fmt_time(a.created_at), color="#409EFF")))

    # 2) 工单动态
    orders = (await db.execute(
        select(WorkOrder).order_by(desc(WorkOrder.id)).limit(limit)
    )).scalars().all()
    for w in orders:
        who = getattr(getattr(w, "creator", None), "username", "用户")
        status_map = {"pending":"待处理","assigned":"已指派","processing":"处理中","pending_verify":"待验收","completed":"已完成","closed":"已关闭"}
        st = status_map.get(w.status, w.status)
        text = f"{who} 提交工单「{w.title}」（{w.order_no}），状态：{st}"
        items.append((w.created_at, ActivityItem(type="workorder", text=text, time=fmt_time(w.created_at), color="#E67E22")))

    # 3) 告警
    alerts = (await db.execute(
        select(Alert).order_by(desc(Alert.created_at)).limit(limit)
    )).scalars().all()
    color_map = {"general":"#67C23A","serious":"#E6A23C","emergency":"#F56C6C"}
    for al in alerts:
        lv = {"general":"一般","serious":"严重","emergency":"紧急"}.get(al.level, al.level)
        text = f"产生{lv}告警：{al.title}"
        items.append((al.created_at, ActivityItem(type="alert", text=text, time=fmt_time(al.created_at), color=color_map.get(al.level, "#67C23A"))))

    # 合并后按时间倒序取前 limit 条
    items.sort(key=lambda x: (x[0] is not None, x[0]), reverse=True)
    return [it for _, it in items[:limit]]
