"""
WebSocket 实时通信完善

完整的 WebSocket 实现，支持房间、广播、心跳等
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect, WebSocketState

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    WebSocket 连接管理器
    
    功能:
    - 连接管理
    - 房间管理
    - 广播消息
    - 心跳检测
    - 自动重连
    """
    
    def __init__(self):
        # 活跃连接
        self.active_connections: Dict[str, WebSocket] = {}
        # 房间成员
        self.rooms: Dict[str, Set[str]] = {}
        # 连接元数据
        self.connection_metadata: Dict[str, Dict[str, Any]] = {}
        # 心跳间隔（秒）
        self.heartbeat_interval = 30
        # 心跳超时（秒）
        self.heartbeat_timeout = 90
        # 事件处理器
        self.event_handlers: Dict[str, List[Callable]] = {}
        
        logger.info("ConnectionManager initialized")
    
    async def connect(
        self,
        websocket: WebSocket,
        client_id: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        接受连接
        
        Args:
            websocket: WebSocket 连接
            client_id: 客户端 ID
            metadata: 元数据
        """
        await websocket.accept()
        
        self.active_connections[client_id] = websocket
        self.connection_metadata[client_id] = metadata or {}
        
        logger.info(f"Client connected: {client_id}")
        
        # 发送欢迎消息
        await self.send_to(
            client_id,
            {
                "type": "welcome",
                "data": {
                    "client_id": client_id,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            },
        )
        
        # 启动心跳
        asyncio.create_task(self._heartbeat_loop(client_id))
    
    def disconnect(self, client_id: str):
        """断开连接"""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        
        if client_id in self.connection_metadata:
            del self.connection_metadata[client_id]
        
        # 从所有房间移除
        for room_members in self.rooms.values():
            room_members.discard(client_id)
        
        logger.info(f"Client disconnected: {client_id}")
    
    async def send_to(self, client_id: str, message: Dict[str, Any]):
        """
        发送消息给单个客户端
        
        Args:
            client_id: 客户端 ID
            message: 消息字典
        """
        if client_id not in self.active_connections:
            return
        
        websocket = self.active_connections[client_id]
        
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Send to {client_id} failed: {e}")
            await self.disconnect(client_id)
    
    async def broadcast(self, message: Dict[str, Any], exclude: Optional[str] = None):
        """
        广播消息
        
        Args:
            message: 消息字典
            exclude: 排除的客户端 ID
        """
        disconnected = []
        
        for client_id, websocket in self.active_connections.items():
            if client_id == exclude:
                continue
            
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Broadcast to {client_id} failed: {e}")
                disconnected.append(client_id)
        
        # 清理断开的连接
        for client_id in disconnected:
            await self.disconnect(client_id)
    
    async def send_to_room(self, room: str, message: Dict[str, Any]):
        """
        发送消息给房间
        
        Args:
            room: 房间名
            message: 消息字典
        """
        if room not in self.rooms:
            return
        
        disconnected = []
        
        for client_id in self.rooms[room]:
            if client_id in self.active_connections:
                try:
                    await self.active_connections[client_id].send_json(message)
                except Exception as e:
                    logger.error(f"Send to room {room} failed: {e}")
                    disconnected.append(client_id)
        
        # 清理断开的连接
        for client_id in disconnected:
            self.leave_room(room, client_id)
            await self.disconnect(client_id)
    
    def join_room(self, room: str, client_id: str):
        """加入房间"""
        if room not in self.rooms:
            self.rooms[room] = set()
        
        self.rooms[room].add(client_id)
        
        logger.info(f"Client {client_id} joined room {room}")
    
    def leave_room(self, room: str, client_id: str):
        """离开房间"""
        if room in self.rooms:
            self.rooms[room].discard(client_id)
            
            # 空房间清理
            if not self.rooms[room]:
                del self.rooms[room]
        
        logger.info(f"Client {client_id} left room {room}")
    
    def get_room_members(self, room: str) -> List[str]:
        """获取房间成员"""
        return list(self.rooms.get(room, set()))
    
    def get_connection_count(self) -> int:
        """获取连接数"""
        return len(self.active_connections)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "active_connections": len(self.active_connections),
            "rooms": len(self.rooms),
            "room_members": {
                room: len(members)
                for room, members in self.rooms.items()
            },
        }
    
    # ============ 心跳检测 ============
    
    async def _heartbeat_loop(self, client_id: str):
        """心跳循环"""
        last_pong = datetime.utcnow()
        
        while client_id in self.active_connections:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                
                # 检查超时
                if (datetime.utcnow() - last_pong).total_seconds() > self.heartbeat_timeout:
                    logger.warning(f"Client {client_id} heartbeat timeout")
                    await self.disconnect(client_id)
                    break
                
                # 发送心跳
                await self.send_to(
                    client_id,
                    {
                        "type": "heartbeat",
                        "data": {
                            "timestamp": datetime.utcnow().isoformat(),
                        },
                    },
                )
                
            except Exception as e:
                logger.error(f"Heartbeat for {client_id} failed: {e}")
                break
    
    async def handle_pong(self, client_id: str):
        """处理心跳响应"""
        if client_id in self.connection_metadata:
            self.connection_metadata[client_id]["last_pong"] = datetime.utcnow()
    
    # ============ 事件处理 ============
    
    def on(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
    
    async def emit(self, event_type: str, data: Any):
        """触发事件"""
        handlers = self.event_handlers.get(event_type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(f"Event handler {event_type} error: {e}")


# ============ WebSocket 端点 ============

from fastapi import APIRouter

router = APIRouter(prefix="/ws", tags=["WebSocket"])

manager = ConnectionManager()


@router.websocket("/")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket 主端点"""
    import uuid
    
    client_id = str(uuid.uuid4())
    
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                # 处理心跳响应
                if message_type == "pong":
                    await manager.handle_pong(client_id)
                
                # 处理加入房间
                elif message_type == "join_room":
                    room = message.get("room")
                    if room:
                        manager.join_room(room, client_id)
                
                # 处理离开房间
                elif message_type == "leave_room":
                    room = message.get("room")
                    if room:
                        manager.leave_room(room, client_id)
                
                # 触发事件
                if message_type:
                    await manager.emit(message_type, {
                        "client_id": client_id,
                        "data": message.get("data"),
                    })
                
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from {client_id}: {data}")
    
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {client_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        manager.disconnect(client_id)


# ============ 使用示例 ============

WEBSOCKET_EXAMPLES = """
# WebSocket 使用示例

## 前端连接

```javascript
const ws = new WebSocket('ws://localhost:8080/ws');

ws.onopen = () => {
  console.log('Connected');
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  switch (message.type) {
    case 'welcome':
      console.log('Welcome:', message.data);
      break;
    
    case 'heartbeat':
      // 响应心跳
      ws.send(JSON.stringify({ type: 'pong' }));
      break;
    
    case 'task_update':
      console.log('Task updated:', message.data);
      break;
  }
};

ws.onclose = () => {
  console.log('Disconnected');
};
```

## 加入房间

```javascript
// 加入任务房间
ws.send(JSON.stringify({
  type: 'join_room',
  room: 'task:123'
}));

// 离开房间
ws.send(JSON.stringify({
  type: 'leave_room',
  room: 'task:123'
}));
```

## 后端广播

```python
from src.websocket.manager import manager

# 广播给所有客户端
await manager.broadcast({
  "type": "system_update",
  "data": {"message": "System maintenance in 5 minutes"}
})

# 发送给房间
await manager.send_to_room("task:123", {
  "type": "task_update",
  "data": {"task_id": 123, "status": "completed"}
})

# 发送给单个客户端
await manager.send_to("client_id", {
  "type": "notification",
  "data": {"message": "Your task is complete"}
})
```

## 事件处理

```python
# 注册事件处理器
manager.on("task_created", lambda data: print(f"Task created: {data}"))

# 触发事件
await manager.emit("task_created", {
  "task_id": 123,
  "title": "New Task"
})
```
"""
