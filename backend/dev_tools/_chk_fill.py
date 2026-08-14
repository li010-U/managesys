# -*- coding: utf-8 -*-
import asyncio, sys, os
sys.path.insert(0, os.getcwd())
async def main():
    from sqlalchemy import select
    from app.models.business_system import BusinessSystem
    from app.api.v1.systems import _fill_system
    from app.schemas.business import BusinessSystemResponse
    from app.db.session import async_session_factory
    async with async_session_factory() as db:
        res = await db.execute(select(BusinessSystem).order_by(BusinessSystem.id).limit(3))
        for it in res.scalars().all():
            r = _fill_system(BusinessSystemResponse.model_validate(it), it)
            print(it.name, "count=", r.device_count, "devs=", [ (d.id,d.name) for d in r.deployed_devices ])
asyncio.run(main())
