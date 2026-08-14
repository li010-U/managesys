# -*- coding: utf-8 -*-
import asyncio, sys
async def main():
    from sqlalchemy import select, desc
    from app.models.audit_log import AuditLog
    from app.models.work_order import WorkOrder
    from app.models.alert import Alert
    from app.db.session import async_session_factory
    async with async_session_factory() as db:
        n_a = len((await db.execute(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(12))).scalars().all())
        n_w = len((await db.execute(select(WorkOrder).order_by(desc(WorkOrder.id)).limit(12))).scalars().all())
        n_al = len((await db.execute(select(Alert).order_by(desc(Alert.created_at)).limit(12))).scalars().all())
        print("audit(<=12):", n_a, "workorders(<=12):", n_w, "alerts(<=12):", n_al)
asyncio.run(main())
