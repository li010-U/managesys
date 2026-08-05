"""AI 桌宠助手 API 路由"""
from typing import Optional
from fastapi import APIRouter, Depends, Request
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

import asyncio

from app.core.concurrency import sse_semaphore

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
    request: Request,
    interval: int = 6,
    _current_user: User = Depends(get_current_user),
):
    """实时 SSE 推送，包含数据快照 + 提醒/建议。

    为避免“点快了加载不出来”与多人同时在线时资源恜死：
    - 用 SSE 信号量限制并发长连接数量，超出后返回 503。
    - 每次循环检测客户端断开，断开不再等待下一个 tick，快速释放连接与数据库会话。
    """
    sem = None
    try:
        sem = sse_semaphore()
        await asyncio.wait_for(sem.acquire(), timeout=2.0)
    except asyncio.TimeoutError:
        return JSONResponse(status_code=503, content={"detail": "实时推送连接已满，请稍后重试"})
    except (RuntimeError, ValueError):
        sem = None

    async def event_generator():
        counter = 0
        try:
            while True:
                if await request.is_disconnected():
                    return
                payload = await _produce(counter)
                yield f"data: {payload}\n\n"
                counter += 1
                if await request.is_disconnected():
                    return
                await asyncio.sleep(max(2, interval))
        except asyncio.CancelledError:
            raise
        except Exception:
            yield f"data: [DONE]\n\n"
        finally:
            if sem is not None:
                try:
                    sem.release()
                except (RuntimeError, ValueError):
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _produce(seq: int) -> str:
    import json

    from app.db.session import async_session_factory

    payload_data = {}
    # ????????????????????????????
    async with async_session_factory() as db:
        service = AssistantService(db)
        snapshot = await service.build_snapshot()
        payload_data = {
            "seq": seq,
            "snapshot": snapshot,
            "reminders": service.generate_reminders(snapshot),
            "advisor": service.generate_advisor(snapshot),
        }
    return json.dumps(payload_data, ensure_ascii=False)

