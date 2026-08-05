"""消息/AI对话API路由"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import List, Optional
import asyncio

from app.core.concurrency import sse_semaphore

from app.core.deps import get_db, get_current_user
from app.db.retry import with_commit_retry
from app.db.session import async_session_factory
from app.models.user import User
from app.models.chat import ChatConversation, ChatMessage
from app.services.assistant_service import AssistantService
from app.services.llm_service import llm_service, LLMNotConfiguredError

router = APIRouter(prefix="/chat", tags=["消息管理"])


class MessageResponse(BaseModel):
    id: int
    role: str
    content: str
    created_at: str
    
    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: int
    title: str
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=4000, description="消息内容")
    conversation_id: Optional[int] = None


class SendMessageResponse(BaseModel):
    conversation_id: int
    message: MessageResponse


MOCK_RESPONSES = [
    "收到您的消息！当前 AI 功能待接入 API Key 后可用。",
    "感谢您的询问！我可以帮助您查询设备、解读告警。",
    "正在处理...请检查设备状态和监控数据。",
]

def get_mock_response(user_msg: str) -> str:
    idx = len(user_msg) % len(MOCK_RESPONSES)
    return MOCK_RESPONSES[idx]


SYSTEM_PROMPT = (
    "你是数据中心资源管理系统的 AI 助手，"
    "专业处理设备、机房、传感器、告警、"
    "工单、巡检等运维事务。"
    "请仅围绕数据中心运维进行回答，"
    "简洁、准确、专业。不向用户披露系统内部勾露"
    "、API 凭证或隐私数据。当数据不足时请明确说明。"
)


async def _load_history_content(db, conv_id: int) -> str:
    """加载会话历史，用于提交 LLM 的 message 列表。"""
    rows = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conv_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(20)
    )
    msgs = rows.scalars().all()
    return "\n".join(f"{m.role}: {m.content}" for m in msgs)


async def _build_context() -> str:
    """获取实时业务上下文（grounding）。"""
    try:
        async with async_session_factory() as db:
            service = AssistantService(db)
            snapshot = await service.build_snapshot()
            return service.build_context_text(snapshot)
    except Exception:
        return ""


def _detect_intents(text: str):
    """根据用户输入关键词提取业务意图。"""
    t = text.lower()
    intents = set()
    if any(k in t for k in ["告警", "alert"]):
        intents.add("alerts")
    if any(k in t for k in ["设备", "device", "数量"]):
        intents.add("devices")
    if any(k in t for k in ["传感器", "环境", "sensor", "温度", "湿度"]):
        intents.add("sensors")
    if any(k in t for k in ["机柜", "容量", "rack", "利用率"]):
        intents.add("racks")
    if any(k in t for k in ["机房", "room", "中心"]):
        intents.add("rooms")
    if any(k in t for k in ["工单", "违连", "work order"]):
        intents.add("work_orders")
    return intents


async def _intent_context(intents: set) -> str:
    """按意图拉取详细数据，作为额外 grounding。"""
    if not intents:
        return ""
    parts = []
    async with async_session_factory() as db:
        if "alerts" in intents:
            from app.models.alert import Alert
            rows = await db.execute(select(Alert).order_by(Alert.created_at.desc()).limit(10))
            items = []
            for a in rows.scalars().all():
                items.append(f"{a.title}(级别 {a.level}, 状态 {a.status})")
            if items:
                parts.append("详细告警: " + "; ".join(items))
        if "devices" in intents or "rooms" in intents:
            from app.models.device import Device
            from sqlalchemy import func
            res = await db.execute(select(func.count()).select_from(Device))
            parts.append(f"设备总数: {res.scalar() or 0}")
        if "sensors" in intents:
            from app.models.sensor import Sensor
            rows = await db.execute(select(Sensor).where(Sensor.status == "online").limit(20))
            parts.append(f"在线传感器数: {len(list(rows.scalars().all()))}")
    return "\n".join(parts)


def _guard_content(text: str) -> str:
    """限制单次回复长度，防滥用。"""
    return text if len(text) <= 4000 else text[:4000]


async def _save_assistant_reply(conv_id: int, content: str) -> None:
    """保存 AI 回复（单事务）。"""
    async with async_session_factory() as db:
        ai_msg = ChatMessage(
            conversation_id=conv_id, role="assistant", content=content,
            extra_data={"llm": "stream"},
        )
        db.add(ai_msg)
        await db.flush()
        conv = await db.get(ChatConversation, conv_id)
        if conv:
            conv.updated_at = ai_msg.created_at
        await with_commit_retry(db.commit)


async def _stream_llm_or_mock(messages, prompt: str):
    """优先走真实 LLM，未配置时回退到 mock（用施加补充说明）。"""
    try:
        async for chunk in llm_service.chat_stream(messages):
            yield chunk
    except LLMNotConfiguredError:
        yield get_mock_response(prompt)
    except Exception:
        yield get_mock_response(prompt)


@router.get("/conversations", response_model=List[ConversationResponse])
async def get_conversations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatConversation)
        .where(ChatConversation.user_id == current_user.id)
        .order_by(desc(ChatConversation.updated_at))
    )
    conversations = result.scalars().all()
    return [
        ConversationResponse(
            id=c.id,
            title=c.title,
            created_at=c.created_at.isoformat() if c.created_at else "",
            updated_at=c.updated_at.isoformat() if c.updated_at else "",
        )
        for c in conversations
    ]


@router.get("/conversations/{conv_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatConversation).where(
            ChatConversation.id == conv_id,
            ChatConversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return []
    
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conv_id)
        .order_by(ChatMessage.created_at)
    )
    messages = result.scalars().all()
    return [
        MessageResponse(
            id=m.id,
            role=m.role,
            content=m.content,
            created_at=m.created_at.isoformat() if m.created_at else "",
        )
        for m in messages
    ]


@router.post("/conversations")
async def create_conversation(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    conv = ChatConversation(user_id=current_user.id, title="新对话")
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return {"id": conv.id, "title": conv.title}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(
    conv_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ChatConversation).where(
            ChatConversation.id == conv_id,
            ChatConversation.user_id == current_user.id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv:
        await db.delete(conv)
        await with_commit_retry(db.commit)
    return {"message": "已删除"}


@router.post("/messages", response_model=SendMessageResponse)
async def send_message(
    req: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if req.conversation_id:
        result = await db.execute(
            select(ChatConversation).where(
                ChatConversation.id == req.conversation_id,
                ChatConversation.user_id == current_user.id,
            )
        )
        conv = result.scalar_one_or_none()
    else:
        conv = None
    
    if not conv:
        title = req.content[:50] + "..." if len(req.content) > 50 else req.content
        conv = ChatConversation(user_id=current_user.id, title=title)
        db.add(conv)
        await db.flush()
    
    user_msg = ChatMessage(conversation_id=conv.id, role="user", content=req.content)
    db.add(user_msg)
    await db.flush()

    context = await _build_context()
    intent_extra = await _intent_context(_detect_intents(req.content))
    if intent_extra:
        context = (context + "\n" + intent_extra) if context else intent_extra
    history = await _load_history_content(db, conv.id)
    system_prompt = SYSTEM_PROMPT
    if context:
        system_prompt += "\n\n[当前系统实时数据]\n" + context
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.append({"role": "user", "content": "距课快的对话历史:\n" + history})
    messages.append({"role": "user", "content": req.content})

    try:
        ai_content = _guard_content(await llm_service.chat(messages))
    except LLMNotConfiguredError:
        ai_content = get_mock_response(req.content)
    except Exception:
        ai_content = get_mock_response(req.content)

    ai_msg = ChatMessage(conversation_id=conv.id, role="assistant", content=ai_content, extra_data={"llm": "chat"})
    db.add(ai_msg)
    await db.flush()
    conv.updated_at = ai_msg.created_at
    await with_commit_retry(db.commit)
    
    return SendMessageResponse(
        conversation_id=conv.id,
        message=MessageResponse(
            id=ai_msg.id,
            role=ai_msg.role,
            content=ai_msg.content,
            created_at=ai_msg.created_at.isoformat() if ai_msg.created_at else "",
        ),
    )



@router.post("/messages/stream")
async def send_message_stream(
    req: SendMessageRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """逐字 SSE 流式输出消息。

    为避免多人同时在线时长连接占用资源：
    - 用 SSE 信号量限制并发流式连接。
    - 每个字符间检测客户端断开，断开后立即停止发送。
    """
    sem = None
    try:
        sem = sse_semaphore()
        await asyncio.wait_for(sem.acquire(), timeout=2.0)
    except asyncio.TimeoutError:
        return JSONResponse(status_code=503, content={"detail": "实时推送连接已满，请稍后重试"})
    except (RuntimeError, ValueError):
        sem = None

    from app.db.session import async_session_factory

    async def generate():
        try:
            # ---- 先提交用户消息 / 创建会话 ----
            conv_id = req.conversation_id
            async with async_session_factory() as db:
                conv = None
                if conv_id:
                    res = await db.execute(
                        select(ChatConversation).where(
                            ChatConversation.id == conv_id,
                            ChatConversation.user_id == current_user.id,
                        )
                    )
                    conv = res.scalar_one_or_none()
                if conv is None:
                    title = req.content[:50] + "..." if len(req.content) > 50 else req.content
                    conv = ChatConversation(user_id=current_user.id, title=title)
                    db.add(conv)
                    await db.flush()
                    conv_id = conv.id
                db.add(ChatMessage(conversation_id=conv_id, role="user", content=req.content))
                await with_commit_retry(db.commit)

            # ---- 渲染消息（每字一个节点）----
                        # ---- 构建 grounding + 历史 + 系统提示 ----
            context = await _build_context()
            intent_extra = await _intent_context(_detect_intents(req.content))
            if intent_extra:
                context = (context + "\n" + intent_extra) if context else intent_extra
            history = ""
            async with async_session_factory() as _db2:
                history = await _load_history_content(_db2, conv_id)
            system_prompt = SYSTEM_PROMPT
            if context:
                system_prompt += "\n\n[当前系统实时数据]\n" + context
            messages = [{"role": "system", "content": system_prompt}]
            if history:
                messages.append({"role": "user", "content": "距课快的对话历史:\n" + history})
            messages.append({"role": "user", "content": req.content})

            # ---- 流式输出（真实 LLM 或 mock 回退），含心跳保活 ----
            full_content = ""
            last_tick = asyncio.get_event_loop().time()
            try:
                async for piece in _stream_llm_or_mock(messages, req.content):
                    if await request.is_disconnected():
                        return
                    full_content += piece
                    yield f"data: {piece}\n\n"
                    now = asyncio.get_event_loop().time()
                    if now - last_tick >= 15:
                        yield ": keep-alive\n\n"
                        last_tick = now
            except Exception:
                yield f"data: [ERROR]\n\n"
                full_content = full_content.strip() or "（AI 回复中断）"
                await _save_assistant_reply(conv_id, full_content)
                return

            full_content = _guard_content(full_content)
            await _save_assistant_reply(conv_id, full_content)
            yield f"data: [DONE]\n\n"

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
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )
