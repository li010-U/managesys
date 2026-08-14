# -*- coding: utf-8 -*-
import asyncio, sys
async def main():
    from sqlalchemy import select
    from app.models.facility import Rack
    from app.schemas.facility import RackResponse
    from app.db.session import async_session_factory
    async with async_session_factory() as db:
        res = await db.execute(select(Rack).order_by(Rack.id).limit(3))
        for rack in res.scalars().all():
            r = RackResponse.model_validate(rack)
            print(rack.code, "status=", r.status)
asyncio.run(main())
