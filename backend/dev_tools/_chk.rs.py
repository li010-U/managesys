# -*- coding: utf-8 -*-
import asyncio
async def main():
    from sqlalchemy import select, func
    from app.models.sensor import SensorData, SensorAnomalyGap
    from app.db.session import async_session_factory
    async with async_session_factory() as db:
        sd = (await db.execute(select(func.count()).select_from(SensorData))).scalar() or 0
        sd_old = (await db.execute(select(func.min(SensorData.recorded_at)))).scalar()
        sd_new = (await db.execute(select(func.max(SensorData.recorded_at)))).scalar()
        ag = (await db.execute(select(func.count()).select_from(SensorAnomalyGap))).scalar() or 0
        ag_old = (await db.execute(select(func.min(SensorAnomalyGap.detected_at)))).scalar()
        ag_new = (await db.execute(select(func.max(SensorAnomalyGap.detected_at)))).scalar()
        gaps = (await db.execute(select(SensorAnomalyGap).order_by(SensorAnomalyGap.detected_at.desc()).limit(5))).scalars().all()
        print("sensor_data count:", sd, "oldest:", sd_old, "newest:", sd_new)
        print("anomaly_gap count:", ag, "oldest:", ag_old, "newest:", ag_new)
        for g in gaps:
            print("  gap:", g.id, "sensor", g.sensor_id, "sev", g.severity, "detected", g.detected_at, "remark", (g.remark or "")[:30])
asyncio.run(main())
