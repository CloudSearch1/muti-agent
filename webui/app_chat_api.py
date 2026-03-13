"""
聊天 API 模块 - 数据库持久化版本

提供完整的聊天会话和消息管理功能：
- 会话列表获取
- 消息历史加载（支持分页）
- 新消息保存
- 会话删除
- 错误处理和重试机制
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import crud
from src.db.database import get_db_session
from src.db.models import ChatMessageModel

logger = logging.getLogger(__name__)

# 创建路由器
chat_router = APIRouter(prefix="/api/v1/chat", tags=["聊天管理"])


# ============ 数据模型 ============

class ChatMessageSchema(BaseModel):
    """聊天消息 Schema"""
    id: Optional[int] = None
    session_id: str
    role: str  # user, assistant, system
    content: str
    timestamp: Optional[str] = None
    metadata: Optional[dict] = {}

    class Config:
        from_attributes = True


class ChatSessionSchema(BaseModel):
    """会话摘要 Schema"""
    session_id: str
    last_message_at: Optional[str] = None
    message_count: int
    preview: Optional[str] = None  # 最新消息预览

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    """聊天历史响应"""
    session_id: str
    messages: List[ChatMessageSchema]
    total: int
    has_more: bool


class ChatSessionsResponse(BaseModel):
    """会话列表响应"""
    sessions: List[ChatSessionSchema]
    total: int
    has_more: bool


# ============ API 端点 ============

@chat_router.get("/sessions", response_model=ChatSessionsResponse)
async def get_chat_sessions(
    limit: int = Query(20, ge=1, le=100, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取会话列表
    
    - **limit**: 每页返回的会话数量（1-100）
    - **offset**: 分页偏移量
    """
    try:
        sessions = await crud.get_chat_sessions(db, limit=limit, offset=offset)
        
        # 获取每个会话的最新消息预览
        sessions_with_preview = []
        for session in sessions:
            # 获取最新消息作为预览
            messages = await crud.get_chat_messages_by_session(
                db, session["session_id"], limit=1, offset=0
            )
            preview = messages[0].content[:100] + "..." if messages and len(messages[0].content) > 100 else (messages[0].content if messages else "")
            
            sessions_with_preview.append({
                "session_id": session["session_id"],
                "last_message_at": session["last_message_at"],
                "message_count": session["message_count"],
                "preview": preview
            })
        
        # 获取总会话数（用于判断是否有更多）
        total_result = await db.execute(
            select(func.count(func.distinct(ChatMessageModel.session_id)))
        )
        total = total_result.scalar() or 0
        
        return {
            "sessions": sessions_with_preview,
            "total": total,
            "has_more": offset + limit < total
        }
    except Exception as e:
        logger.error(f"获取会话列表失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取会话列表失败：{str(e)}")


@chat_router.get("/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(
    session_id: str,
    limit: int = Query(50, ge=1, le=200, description="每页数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取聊天历史（支持分页）
    
    - **session_id**: 会话 ID
    - **limit**: 每页返回的消息数量（1-200）
    - **offset**: 分页偏移量（用于加载更多历史消息）
    """
    try:
        # 获取消息
        messages = await crud.get_chat_messages_by_session(
            db, session_id, limit=limit, offset=offset
        )
        
        # 获取总消息数
        count_result = await db.execute(
            select(func.count(ChatMessageModel.id)).where(
                ChatMessageModel.session_id == session_id
            )
        )
        total = count_result.scalar() or 0
        
        # 转换为 Schema
        message_list = [
            {
                "id": msg.id,
                "session_id": msg.session_id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "metadata": msg.metadata or {}
            }
            for msg in messages
        ]
        
        return {
            "session_id": session_id,
            "messages": message_list,
            "total": total,
            "has_more": offset + limit < total
        }
    except Exception as e:
        logger.error(f"获取聊天历史失败 (session={session_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取聊天历史失败：{str(e)}")


@chat_router.post("/messages", response_model=ChatMessageSchema)
async def create_chat_message(
    message_data: dict,
    db: AsyncSession = Depends(get_db_session)
):
    """
    保存新消息
    
    - **session_id**: 会话 ID
    - **role**: 角色（user/assistant/system）
    - **content**: 消息内容
    - **metadata**: 元数据（可选）
    """
    try:
        session_id = message_data.get("session_id")
        role = message_data.get("role")
        content = message_data.get("content")
        metadata = message_data.get("metadata", {})
        
        if not session_id or not role or not content:
            raise HTTPException(status_code=400, detail="缺少必要字段：session_id, role, content")
        
        # 创建消息
        message = await crud.create_chat_message(
            db,
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata
        )
        
        return {
            "id": message.id,
            "session_id": message.session_id,
            "role": message.role,
            "content": message.content,
            "timestamp": message.timestamp.isoformat() if message.timestamp else None,
            "metadata": message.metadata or {}
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"保存消息失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"保存消息失败：{str(e)}")


@chat_router.post("/messages/batch")
async def create_chat_messages_batch(
    messages_data: List[dict],
    db: AsyncSession = Depends(get_db_session)
):
    """
    批量保存消息（用于初始化会话或导入历史）
    
    - **messages**: 消息列表，每条消息包含 session_id, role, content, metadata
    """
    try:
        if not messages_data or len(messages_data) == 0:
            raise HTTPException(status_code=400, detail="消息列表不能为空")
        
        saved_messages = []
        for msg_data in messages_data:
            session_id = msg_data.get("session_id")
            role = msg_data.get("role")
            content = msg_data.get("content")
            metadata = msg_data.get("metadata", {})
            
            if not session_id or not role or not content:
                continue
            
            message = await crud.create_chat_message(
                db,
                session_id=session_id,
                role=role,
                content=content,
                metadata=metadata
            )
            saved_messages.append({
                "id": message.id,
                "session_id": message.session_id,
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp.isoformat() if message.timestamp else None
            })
        
        return {
            "status": "success",
            "saved_count": len(saved_messages),
            "messages": saved_messages
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量保存消息失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"批量保存消息失败：{str(e)}")


@chat_router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    删除会话及其所有消息
    
    - **session_id**: 会话 ID
    """
    try:
        deleted = await crud.delete_chat_session(db, session_id)
        
        if not deleted:
            raise HTTPException(status_code=404, detail="会话不存在")
        
        return {
            "status": "success",
            "message": "会话已删除",
            "session_id": session_id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话失败 (session={session_id}): {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除会话失败：{str(e)}")


@chat_router.get("/stats")
async def get_chat_stats(
    db: AsyncSession = Depends(get_db_session)
):
    """
    获取聊天统计信息
    
    返回：
    - 总会话数
    - 总消息数
    - 按角色统计的消息数
    """
    try:
        stats = await crud.get_chat_stats(db)
        return stats
    except Exception as e:
        logger.error(f"获取聊天统计失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取统计失败：{str(e)}")


# ============ 辅助函数 ============

def generate_session_id(user_id: Optional[str] = None) -> str:
    """
    生成会话 ID
    
    格式：{user_id}_{timestamp}_{random}
    如果 user_id 为空，则使用 default 作为前缀
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    
    if user_id:
        return f"{user_id}_{timestamp}_{unique_id}"
    else:
        return f"default_{timestamp}_{unique_id}"


# 如果需要单独使用这个模块
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    from pydantic import BaseModel
    
    app = FastAPI()
    app.include_router(chat_router)
    
    uvicorn.run(app, host="0.0.0.0", port=8081)
