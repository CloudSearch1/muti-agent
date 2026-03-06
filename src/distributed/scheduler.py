"""
分布式任务调度

支持多节点任务调度和负载均衡
"""

import asyncio
import hashlib
import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class NodeStatus(str, Enum):
    """节点状态"""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    DRAINING = "draining"


@dataclass
class Node:
    """工作节点"""
    id: str
    host: str
    port: int
    status: NodeStatus = NodeStatus.ONLINE
    load: float = 0.0  # 0-100
    tasks_count: int = 0
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_available(self) -> bool:
        """节点是否可用"""
        return (
            self.status == NodeStatus.ONLINE and
            self.load < 80 and
            (datetime.utcnow() - self.last_heartbeat).total_seconds() < 60
        )


@dataclass
class Task:
    """分布式任务"""
    id: str
    type: str
    payload: Dict[str, Any]
    priority: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    scheduled_at: Optional[datetime] = None
    assigned_to: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[Any] = None
    error: Optional[str] = None
    retries: int = 0
    max_retries: int = 3


class DistributedScheduler:
    """
    分布式任务调度器
    
    功能:
    - 节点管理
    - 任务调度
    - 负载均衡
    - 故障转移
    - 任务队列
    """
    
    def __init__(self, node_id: Optional[str] = None):
        self.node_id = node_id or self._generate_node_id()
        self.nodes: Dict[str, Node] = {}
        self.tasks: Dict[str, Task] = {}
        self.task_queue: List[Task] = []
        self.task_handlers: Dict[str, Callable] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        
        logger.info(f"DistributedScheduler initialized: {self.node_id}")
    
    def _generate_node_id(self) -> str:
        """生成节点 ID"""
        import socket
        hostname = socket.gethostname()
        timestamp = str(time.time())
        return hashlib.md5(f"{hostname}:{timestamp}".encode()).hexdigest()[:12]
    
    # ============ 节点管理 ============
    
    def register_node(
        self,
        node_id: str,
        host: str,
        port: int,
        capabilities: Optional[List[str]] = None,
    ):
        """注册节点"""
        node = Node(
            id=node_id,
            host=host,
            port=port,
            capabilities=capabilities or [],
        )
        self.nodes[node_id] = node
        logger.info(f"Node registered: {node_id} at {host}:{port}")
    
    def unregister_node(self, node_id: str):
        """注销节点"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            logger.info(f"Node unregistered: {node_id}")
    
    def update_node_heartbeat(self, node_id: str, load: float, tasks_count: int):
        """更新节点心跳"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.last_heartbeat = datetime.utcnow()
            node.load = load
            node.tasks_count = tasks_count
            
            if load > 80:
                node.status = NodeStatus.BUSY
            elif node.status == NodeStatus.BUSY and load < 60:
                node.status = NodeStatus.ONLINE
    
    def get_available_nodes(self) -> List[Node]:
        """获取可用节点"""
        return [node for node in self.nodes.values() if node.is_available()]
    
    def select_node(self, task: Task) -> Optional[Node]:
        """
        选择最佳节点（负载均衡）
        
        策略:
        - 最少连接数
        - 最低负载
        - 能力匹配
        """
        available = self.get_available_nodes()
        
        if not available:
            return None
        
        # 过滤能力匹配的节点
        if task.type in self.task_handlers:
            available = [
                node for node in available
                if not node.capabilities or task.type in node.capabilities
            ]
        
        if not available:
            return None
        
        # 选择负载最低的节点
        return min(available, key=lambda n: (n.load, n.tasks_count))
    
    # ============ 任务管理 ============
    
    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self.task_handlers[task_type] = handler
        logger.info(f"Task handler registered: {task_type}")
    
    async def submit_task(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: int = 0,
    ) -> str:
        """提交任务"""
        task_id = self._generate_task_id()
        
        task = Task(
            id=task_id,
            type=task_type,
            payload=payload,
            priority=priority,
        )
        
        self.tasks[task_id] = task
        self.task_queue.append(task)
        
        # 按优先级排序
        self.task_queue.sort(key=lambda t: (-t.priority, t.created_at))
        
        logger.info(f"Task submitted: {task_id} (type={task_type}, priority={priority})")
        
        return task_id
    
    def _generate_task_id(self) -> str:
        """生成任务 ID"""
        import uuid
        return str(uuid.uuid4())
    
    async def process_task(self, task: Task):
        """处理任务"""
        if task.type not in self.task_handlers:
            task.status = "failed"
            task.error = f"No handler for task type: {task.type}"
            return
        
        handler = self.task_handlers[task.type]
        
        try:
            task.status = "running"
            task.assigned_to = self.node_id
            
            # 执行任务
            if asyncio.iscoroutinefunction(handler):
                result = await handler(task.payload)
            else:
                result = handler(task.payload)
            
            task.status = "completed"
            task.result = result
            
            logger.info(f"Task completed: {task.id}")
            
        except Exception as e:
            task.retries += 1
            
            if task.retries < task.max_retries:
                task.status = "pending"
                task.assigned_to = None
                self.task_queue.append(task)
                logger.warning(f"Task failed, retrying: {task.id} (retry {task.retries}/{task.max_retries})")
            else:
                task.status = "failed"
                task.error = str(e)
                logger.error(f"Task failed permanently: {task.id} - {e}")
    
    # ============ 调度循环 ============
    
    async def start(self):
        """启动调度器"""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduler started")
    
    async def stop(self):
        """停止调度器"""
        self._running = False
        
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Scheduler stopped")
    
    async def _scheduler_loop(self):
        """调度循环"""
        while self._running:
            try:
                # 处理任务队列
                if self.task_queue:
                    task = self.task_queue.pop(0)
                    
                    # 选择节点
                    if task.assigned_to is None:
                        node = self.select_node(task)
                        
                        if node:
                            task.assigned_to = node.id
                            # TODO: 发送到远程节点
                            asyncio.create_task(self.process_task(task))
                        else:
                            # 没有可用节点，重新入队
                            self.task_queue.append(task)
                    else:
                        # 已分配的任务
                        asyncio.create_task(self.process_task(task))
                
                # 清理过期节点
                self._cleanup_nodes()
                
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(1)
    
    def _cleanup_nodes(self):
        """清理过期节点"""
        now = datetime.utcnow()
        
        for node_id, node in list(self.nodes.items()):
            if (now - node.last_heartbeat).total_seconds() > 120:
                node.status = NodeStatus.OFFLINE
                logger.warning(f"Node timeout: {node_id}")
    
    # ============ 统计 ============
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计"""
        return {
            "node_id": self.node_id,
            "total_nodes": len(self.nodes),
            "online_nodes": len([n for n in self.nodes.values() if n.status == NodeStatus.ONLINE]),
            "busy_nodes": len([n for n in self.nodes.values() if n.status == NodeStatus.BUSY]),
            "pending_tasks": len([t for t in self.tasks.values() if t.status == "pending"]),
            "running_tasks": len([t for t in self.tasks.values() if t.status == "running"]),
            "completed_tasks": len([t for t in self.tasks.values() if t.status == "completed"]),
            "failed_tasks": len([t for t in self.tasks.values() if t.status == "failed"]),
        }


# ============ 全局调度器 ============

_scheduler: Optional[DistributedScheduler] = None


def get_scheduler() -> DistributedScheduler:
    """获取调度器"""
    global _scheduler
    if _scheduler is None:
        _scheduler = DistributedScheduler()
    return _scheduler


async def init_scheduler(**kwargs) -> DistributedScheduler:
    """初始化调度器"""
    global _scheduler
    _scheduler = DistributedScheduler(**kwargs)
    await _scheduler.start()
    logger.info("Scheduler initialized")
    return _scheduler


async def close_scheduler():
    """关闭调度器"""
    global _scheduler
    if _scheduler:
        await _scheduler.stop()
        _scheduler = None
