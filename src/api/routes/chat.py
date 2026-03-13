"""
聊天消息路由

提供聊天消息持久化相关的 API 端点
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.crud import (
    create_chat_message,
    delete_chat_session,
    get_chat_message_by_id,
    get_chat_messages_by_session,
    get_chat_sessions,
    get_chat_stats,
)
from ...db.database import get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["聊天消息"])


# ===========================================
# 请求/响应模型
# ===========================================


class ChatMessageCreate(BaseModel):
    """创建消息请求"""

    session_id: str = Field(..., description="会话 ID", min_length=1, max_length=100)
    role: str = Field(..., description="角色：user/assistant/system", pattern="^(user|assistant|system)$")
    content: str = Field(..., description="消息内容", min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class ChatMessageResponse(BaseModel):
    """消息响应"""

    id: int
    session_id: str
    role: str
    content: str
    timestamp: str
    metadata: dict[str, Any]

    class Config:
        from_attributes = True


class ChatSessionResponse(BaseModel):
    """会话响应"""

    session_id: str
    last_message_at: str | None
    message_count: int


class ChatSessionDetailResponse(BaseModel):
    """会话详情响应"""

    session_id: str
    messages: list[ChatMessageResponse]
    total_count: int


class ChatStatsResponse(BaseModel):
    """聊天统计响应"""

    total_sessions: int
    total_messages: int
    messages_by_role: dict[str, int]


# ===========================================
# 依赖注入
# ===========================================


async def get_db() -> AsyncSession:
    """获取数据库会话"""
    async for session in get_db_session():
        yield session


# ===========================================
# API 端点
# ===========================================


@router.get(
    "/sessions",
    response_model=list[ChatSessionResponse],
    summary="获取会话列表",
    response_description="会话列表",
)
async def list_chat_sessions(
    limit: int = Query(50, ge=1, le=200, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取所有聊天会话列表

    - **limit**: 返回的会话数量（默认 50，最大 200）
    - **offset**: 分页偏移量
    - 按最新消息时间降序排序
    """
    try:
        sessions = await get_chat_sessions(db, limit=limit, offset=offset)
        return sessions
    except Exception as e:
        logger.error(f"获取会话列表失败：{e}")
        raise HTTPException(status_code=500, detail=f"获取会话列表失败：{str(e)}")


@router.get(
    "/sessions/{session_id}",
    response_model=ChatSessionDetailResponse,
    summary="获取会话消息历史",
    response_description="会话消息历史",
)
async def get_chat_session(
    session_id: str,
    limit: int = Query(100, ge=1, le=500, description="返回消息数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
):
    """
    获取指定会话的消息历史

    - **session_id**: 会话 ID
    - **limit**: 返回的消息数量（默认 100，最大 500）
    - **offset**: 分页偏移量
    - 消息按时间升序排序
    """
    try:
        messages = await get_chat_messages_by_session(db, session_id, limit=limit, offset=offset)
        return {
            "session_id": session_id,
            "messages": [ChatMessageResponse.model_validate(msg) for msg in messages],
            "total_count": len(messages),
        }
    except Exception as e:
        logger.error(f"获取会话 {session_id} 失败：{e}")
        raise HTTPException(status_code=500, detail=f"获取会话失败：{str(e)}")


@router.post(
    "/messages",
    response_model=ChatMessageResponse,
    summary="保存新消息",
    response_description="创建的消息",
    status_code=201,
)
async def save_chat_message(
    message_data: ChatMessageCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    保存新的聊天消息到数据库

    - **session_id**: 会话 ID
    - **role**: 消息角色（user/assistant/system）
    - **content**: 消息内容
    - **metadata**: 可选的元数据（JSON 格式）
    """
    try:
        message = await create_chat_message(
            db,
            session_id=message_data.session_id,
            role=message_data.role,
            content=message_data.content,
            metadata=message_data.metadata,
        )
        logger.info(f"消息已保存：session={message_data.session_id}, id={message.id}")
        return ChatMessageResponse.model_validate(message)
    except Exception as e:
        logger.error(f"保存消息失败：{e}")
        raise HTTPException(status_code=500, detail=f"保存消息失败：{str(e)}")


@router.delete(
    "/sessions/{session_id}",
    summary="删除会话",
    response_description="删除结果",
)
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    删除指定会话及其所有消息

    - **session_id**: 要删除的会话 ID
    - 此操作不可恢复
    """
    try:
        success = await delete_chat_session(db, session_id)
        if not success:
            raise HTTPException(status_code=404, detail=f"会话 {session_id} 不存在")
        return {"status": "deleted", "session_id": session_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除会话 {session_id} 失败：{e}")
        raise HTTPException(status_code=500, detail=f"删除会话失败：{str(e)}")


@router.get(
    "/messages/{message_id}",
    response_model=ChatMessageResponse,
    summary="获取单条消息",
    response_description="消息详情",
)
async def get_message(
    message_id: int,
    db: AsyncSession = Depends(get_db),
):
    """
    根据 ID 获取单条消息

    - **message_id**: 消息 ID
    """
    try:
        message = await get_chat_message_by_id(db, message_id)
        if not message:
            raise HTTPException(status_code=404, detail=f"消息 {message_id} 不存在")
        return ChatMessageResponse.model_validate(message)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取消息 {message_id} 失败：{e}")
        raise HTTPException(status_code=500, detail=f"获取消息失败：{str(e)}")


@router.get(
    "/stats",
    response_model=ChatStatsResponse,
    summary="获取聊天统计",
    response_description="聊天统计信息",
)
async def get_chat_statistics(
    db: AsyncSession = Depends(get_db),
):
    """
    获取聊天系统的统计信息

    包括：
    - 总会话数
    - 总消息数
    - 按角色分类的消息数量
    """
    try:
        stats = await get_chat_stats(db)
        return ChatStatsResponse(**stats)
    except Exception as e:
        logger.error(f"获取统计信息失败：{e}")
        raise HTTPException(status_code=500, detail=f"获取统计信息失败：{str(e)}")


# ===========================================
# WebSocket 支持
# ===========================================


class WebSocketManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        """接受 WebSocket 连接"""
        await websocket.accept()
        if session_id not in self.active_connections:
            self.active_connections[session_id] = []
        self.active_connections[session_id].append(websocket)
        logger.info(f"WebSocket 连接：session={session_id}, total={len(self.active_connections[session_id])}")

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        """断开 WebSocket 连接"""
        if session_id in self.active_connections:
            if websocket in self.active_connections[session_id]:
                self.active_connections[session_id].remove(websocket)
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        logger.info(f"WebSocket 断开：session={session_id}")

    async def broadcast_to_session(self, session_id: str, message: dict) -> None:
        """向指定会话的所有连接广播消息"""
        if session_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[session_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    disconnected.append(connection)
            # 清理断开的连接
            for conn in disconnected:
                self.disconnect(conn, session_id)

    async def send_personal_message(self, websocket: WebSocket, message: dict) -> None:
        """发送个人消息"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"发送 WebSocket 消息失败：{e}")


# WebSocket 管理器实例
websocket_manager = WebSocketManager()


@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    WebSocket 端点 - 实时消息持久化和广播

    支持：
    - 实时保存消息到数据库
    - 向同一会话的其他连接广播消息
    - 心跳检测
    """
    await websocket_manager.connect(websocket, session_id)
    try:
        while True:
            try:
                data = await websocket.receive_json()
                
                # 处理不同类型的消息
                message_type = data.get("type", "message")
                
                if message_type == "message":
                    # 保存消息到数据库
                    role = data.get("role", "user")
                    content = data.get("content", "")
                    metadata = data.get("metadata", {})
                    
                    if not content:
                        await websocket.send_json({
                            "type": "error",
                            "error": "消息内容不能为空"
                        })
                        continue
                    
                    # 保存到数据库
                    message = await create_chat_message(
                        db,
                        session_id=session_id,
                        role=role,
                        content=content,
                        metadata=metadata,
                    )
                    
                    # 广播给同一会话的其他连接
                    await websocket_manager.broadcast_to_session(
                        session_id,
                        {
                            "type": "message_saved",
                            "message": ChatMessageResponse.model_validate(message).model_dump(),
                        }
                    )
                    
                elif message_type == "heartbeat":
                    # 心跳响应
                    await websocket.send_json({
                        "type": "heartbeat_ack",
                        "timestamp": datetime.now().isoformat(),
                    })
                    
                elif message_type == "get_history":
                    # 获取历史消息
                    limit = data.get("limit", 50)
                    messages = await get_chat_messages_by_session(db, session_id, limit=limit)
                    await websocket.send_json({
                        "type": "history",
                        "messages": [ChatMessageResponse.model_validate(msg).model_dump() for msg in messages],
                    })
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket 消息处理错误：{e}")
                await websocket.send_json({
                    "type": "error",
                    "error": str(e),
                })
    finally:
        websocket_manager.disconnect(websocket, session_id)
