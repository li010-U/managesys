"""AI 桌宠助手 API 路由"""
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

import asyncio

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.assistant_service import AssistantService

router = APIRouter(prefix="/assistant", tags=["AI 桌宠助手"])


@router.get("/snapshot")
async def assistant_snapshot(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """返回一次实时统计数据快照 + 主动提醒/建议。"""
    service = AssistantService(db)
    snapshot = await service.build_snapshot()
    reminders = service.generate_reminders(snapshot)
    advisor = service.generate_advisor(snapshot)
    return {
        "snapshot": snapshot,
        "reminders": reminders,
        "advisor": advisor,
    }


@router.get("/stream")
async def assistant_stream(
    interval: int = 6,
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """SSE 长连接：周期性推送实时快照 + 主动提醒/建议。"""

    async def event_generator():
        yield f"data: {await _produce(db, 0)}\n\n"
        counter = 1
        while True:
            await asyncio.sleep(max(2, interval))
            try:
                yield f"data: {await _produce(db, counter)}\n\n"
                counter += 1
            except Exception:
                yield f"data: [DONE]\n\n"
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _produce(db: AsyncSession, seq: int) -> str:
    import json

    service = AssistantService(db)
    snapshot = await service.build_snapshot()
    reminders = service.generate_reminders(snapshot)
    advisor = service.generate_advisor(snapshot)
    return json.dumps(
        {
            "seq": seq,
            "snapshot": snapshot,
            "reminders": reminders,
            "advisor": advisor,
        },
        ensure_ascii=False,
    )
