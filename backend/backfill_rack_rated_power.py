# -*- coding: utf-8 -*-
"""Backfill racks.rated_power missing/zero with a sensible default.

Runs once against the live SQLite DB (idempotent). Sets rated_power to a
default (10 kW) when NULL or <= 0, so power_util_pct is not misleadingly 0.
"""
import asyncio
import sys
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import async_session_factory
from app.models.facility import Rack

DEFAULT_RATED = 10.0


async def main() -> None:
    count = 0
    async with async_session_factory() as s:
        racks = (await s.execute(select(Rack))).scalars().all()
        for r in racks:
            if not r.rated_power or r.rated_power <= 0:
                r.rated_power = DEFAULT_RATED
                count += 1
        await s.commit()
    print(f"backfilled {count} racks to {DEFAULT_RATED} kW")


if __name__ == "__main__":
    asyncio.run(main())
