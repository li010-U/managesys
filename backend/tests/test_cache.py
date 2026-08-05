"""core ???????"""
import asyncio

from app.core.cache import AsyncTTLSingleFlight


def test_singleflight_runs_builder_once():
    async def run():
        cache = AsyncTTLSingleFlight(ttl_seconds=4.0)
        calls = {"n": 0}

        async def loader():
            calls["n"] += 1
            await asyncio.sleep(0.01)
            return {"v": calls["n"]}

        results = await asyncio.gather(*(cache.get_or_load(loader) for _ in range(5)))
        assert all(r == {"v": 1} for r in results)
        assert calls["n"] == 1
        # ????
        assert await cache.get_or_load(loader) == {"v": 1}
        assert calls["n"] == 1

    asyncio.run(run())


def test_ttl_expiry_rebuilds():
    async def run():
        cache = AsyncTTLSingleFlight(ttl_seconds=0.05)
        calls = {"n": 0}

        async def loader():
            calls["n"] += 1
            return calls["n"]

        assert await cache.get_or_load(loader) == 1
        assert await cache.get_or_load(loader) == 1
        await asyncio.sleep(0.1)
        assert await cache.get_or_load(loader) == 2

    asyncio.run(run())
