"""消息/AI对话API路由"""
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional
import asyncio

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.chat import ChatConversation, ChatMessage

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
    content: str
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
        await db.commit()
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
    
    # TODO: 接入LLM
    ai_content = get_mock_response(req.content)
    
    ai_msg = ChatMessage(conversation_id=conv.id, role="assistant", content=ai_content)
    db.add(ai_msg)
    await db.flush()
    conv.updated_at = ai_msg.created_at
    await db.commit()
    
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
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    async def generate():
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
        
        # TODO: 接入LLM
        full_content = get_mock_response(req.content)
        for char in full_content:
            yield f"data: {char}\n\n"
            await asyncio.sleep(0.02)
        
        ai_msg = ChatMessage(conversation_id=conv.id, role="assistant", content=full_content)
        db.add(ai_msg)
        await db.flush()
        conv.updated_at = ai_msg.created_at
        await db.commit()
        
        yield f"data: [DONE]\n\n"
    
    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )