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
from app.services.assistant_service import AssistantService, get_cached_snapshot

router = APIRouter(prefix="/assistant", tags=["AI 桌宠助手"])


@router.get("/snapshot")
async def assistant_snapshot(
    _current_user: User = Depends(get_current_user),
):
    """\u8fd4\u56de\u4e00\u6b21\u5b9e\u65f6\u7edf\u8ba1\u6570\u636e\u5feb\u7167 + \u4e3b\u52a8\u63d0\u9192/\u5efa\u8bae\uff08\u5e26\u77ed TTL \u7f13\u5b58\uff09\u3002"""
    snapshot = await get_cached_snapshot()
    service = AssistantService.__new__(AssistantService)
    service.db = None  # reminders/advisor \u4ec5\u4f9d\u8d56\u5feb\u7167\u5b57\u5178\uff0c\u65e0\u9700\u4f1a\u8bdd
    return {
        "snapshot": snapshot,
        "reminders": service.generate_reminders(snapshot),
        "advisor": service.generate_advisor(snapshot),
    }


@router.get("/stream")
async def assistant_stream(
    request: Request,
    interval: int = 10,
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

    snapshot = await get_cached_snapshot()
    service = AssistantService.__new__(AssistantService)
    service.db = None  # reminders/advisor \u4ec5\u4f9d\u8d56\u5feb\u7167\u5b57\u5178\uff0c\u65e0\u9700\u4f1a\u8bdd
    payload_data = {
        "seq": seq,
        "snapshot": snapshot,
        "reminders": service.generate_reminders(snapshot),
        "advisor": service.generate_advisor(snapshot),
    }
    return json.dumps(payload_data, ensure_ascii=False)
