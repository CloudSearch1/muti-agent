"""
Memory API 路由

提供完整的记忆系统 CRUD API：
- 短期记忆（Redis）
- 长期记忆（数据库）
- 向量记忆（RAG）
"""

from datetime import datetime
from typing import Any, Optional

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.memory import (
    LongTermMemory,
    MemoryImportance,
    MemoryType,
    RAGStore,
    ShortTermMemory,
    create_long_term_memory,
    create_rag_store,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# ===========================================
# 请求/响应模型
# ===========================================


class MemoryStoreRequest(BaseModel):
    """存储记忆请求"""

    content: str = Field(..., description="记忆内容")
    memory_type: str = Field(
        default="episodic",
        description="记忆类型: episodic, semantic, procedural, conversation, task_result",
    )
    storage: str = Field(
        default="long_term",
        description="存储类型: short_term, long_term, vector",
    )
    importance: str = Field(
        default="medium",
        description="重要性: low, medium, high, critical",
    )
    summary: Optional[str] = Field(None, description="摘要")
    tags: list[str] = Field(default_factory=list, description="标签")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")
    agent_id: Optional[str] = Field(None, description="Agent ID")
    session_id: Optional[str] = Field(None, description="会话 ID")
    task_id: Optional[str] = Field(None, description="任务 ID")
    ttl: Optional[int] = Field(None, description="TTL（秒），仅用于短期记忆")


class MemorySearchRequest(BaseModel):
    """搜索记忆请求"""

    query: Optional[str] = Field(None, description="搜索查询")
    memory_type: Optional[str] = Field(None, description="记忆类型过滤")
    importance: Optional[str] = Field(None, description="重要性过滤")
    tags: Optional[list[str]] = Field(None, description="标签过滤")
    agent_id: Optional[str] = Field(None, description="Agent ID 过滤")
    session_id: Optional[str] = Field(None, description="会话 ID 过滤")
    task_id: Optional[str] = Field(None, description="任务 ID 过滤")
    storage: str = Field(
        default="long_term",
        description="存储类型: short_term, long_term, vector",
    )
    limit: int = Field(default=10, ge=1, le=100, description="返回数量限制")
    offset: int = Field(default=0, ge=0, description="偏移量")


class MemoryResponse(BaseModel):
    """记忆响应"""

    id: str
    memory_id: Optional[str] = None
    content: str
    memory_type: Optional[str] = None
    importance: Optional[str] = None
    summary: Optional[str] = None
    tags: list[str] = []
    metadata: dict[str, Any] = {}
    agent_id: Optional[str] = None
    session_id: Optional[str] = None
    task_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    access_count: Optional[int] = None
    similarity_score: Optional[float] = None


class MemoryListResponse(BaseModel):
    """记忆列表响应"""

    memories: list[MemoryResponse]
    total: int
    limit: int
    offset: int


class MemoryStatsResponse(BaseModel):
    """记忆统计响应"""

    storage_type: str
    total_count: int
    by_type: Optional[dict[str, int]] = None
    by_importance: Optional[dict[str, int]] = None
    recently_accessed_24h: Optional[int] = None
    rag_enabled: Optional[bool] = None


# ===========================================
# 全局实例（延迟初始化）
# ===========================================

_short_term_memory: Optional[ShortTermMemory] = None
_long_term_memory: Optional[LongTermMemory] = None
_rag_store: Optional[RAGStore] = None


def get_short_term_memory() -> ShortTermMemory:
    """获取短期记忆实例"""
    global _short_term_memory
    if _short_term_memory is None:
        _short_term_memory = ShortTermMemory()
    return _short_term_memory


def get_long_term_memory() -> LongTermMemory:
    """获取长期记忆实例"""
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = create_long_term_memory()
    return _long_term_memory


async def get_rag_store() -> RAGStore:
    """获取 RAG 存储实例"""
    global _rag_store
    if _rag_store is None:
        _rag_store = create_rag_store()
        await _rag_store.initialize()
    return _rag_store


# ===========================================
# API 端点
# ===========================================


@router.post(
    "/",
    response_model=MemoryResponse,
    summary="存储记忆",
    description="将内容存储到指定的记忆系统中",
)
async def store_memory(request: MemoryStoreRequest):
    """存储记忆"""
    try:
        if request.storage == "short_term":
            # 短期记忆（Redis）
            memory = get_short_term_memory()
            memory_id = f"short_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(request.content) % 10000}"

            await memory.set(
                key=memory_id,
                value={
                    "content": request.content,
                    "memory_type": request.memory_type,
                    "importance": request.importance,
                    "tags": request.tags,
                    "metadata": request.metadata,
                    "agent_id": request.agent_id,
                    "session_id": request.session_id,
                    "task_id": request.task_id,
                    "created_at": datetime.now().isoformat(),
                },
                ttl=request.ttl,
            )

            logger.info(
                "Short-term memory stored",
                memory_id=memory_id,
                content_length=len(request.content),
            )

            return MemoryResponse(
                id=memory_id,
                memory_id=memory_id,
                content=request.content,
                memory_type=request.memory_type,
                importance=request.importance,
                tags=request.tags,
                metadata=request.metadata,
                agent_id=request.agent_id,
                session_id=request.session_id,
                task_id=request.task_id,
                created_at=datetime.now().isoformat(),
            )

        elif request.storage == "vector":
            # 向量记忆（RAG）
            rag = await get_rag_store()
            memory_id = await rag.add_memory(
                content=request.content,
                metadata={
                    "memory_type": request.memory_type,
                    "importance": request.importance,
                    "tags": request.tags,
                    **request.metadata,
                    "agent_id": request.agent_id,
                    "session_id": request.session_id,
                    "task_id": request.task_id,
                },
            )

            logger.info(
                "Vector memory stored",
                memory_id=memory_id,
                content_length=len(request.content),
            )

            return MemoryResponse(
                id=memory_id,
                memory_id=memory_id,
                content=request.content,
                memory_type=request.memory_type,
                importance=request.importance,
                tags=request.tags,
                metadata=request.metadata,
                agent_id=request.agent_id,
                session_id=request.session_id,
                task_id=request.task_id,
                created_at=datetime.now().isoformat(),
            )

        else:
            # 长期记忆（数据库）- 默认
            ltm = get_long_term_memory()

            # 转换枚举类型
            mem_type = MemoryType(request.memory_type)
            imp = MemoryImportance(request.importance)

            memory_id = await ltm.store(
                content=request.content,
                memory_type=mem_type,
                importance=imp,
                summary=request.summary,
                tags=request.tags,
                metadata=request.metadata,
                agent_id=request.agent_id,
                session_id=request.session_id,
                task_id=request.task_id,
            )

            logger.info(
                "Long-term memory stored",
                memory_id=memory_id,
                memory_type=request.memory_type,
                importance=request.importance,
            )

            return MemoryResponse(
                id=memory_id,
                memory_id=memory_id,
                content=request.content,
                memory_type=request.memory_type,
                importance=request.importance,
                summary=request.summary,
                tags=request.tags,
                metadata=request.metadata,
                agent_id=request.agent_id,
                session_id=request.session_id,
                task_id=request.task_id,
                created_at=datetime.now().isoformat(),
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Failed to store memory", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to store memory: {str(e)}")


@router.get(
    "/",
    response_model=MemoryListResponse,
    summary="获取记忆列表",
    description="获取记忆列表，支持过滤和分页",
)
async def list_memories(
    storage: str = Query(default="long_term", description="存储类型"),
    memory_type: Optional[str] = Query(None, description="记忆类型过滤"),
    importance: Optional[str] = Query(None, description="重要性过滤"),
    agent_id: Optional[str] = Query(None, description="Agent ID 过滤"),
    session_id: Optional[str] = Query(None, description="会话 ID 过滤"),
    limit: int = Query(default=10, ge=1, le=100, description="数量限制"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
):
    """获取记忆列表"""
    try:
        if storage == "short_term":
            # 短期记忆不支持列表查询
            return MemoryListResponse(
                memories=[],
                total=0,
                limit=limit,
                offset=offset,
            )

        elif storage == "vector":
            # 向量存储返回空列表（需要搜索）
            return MemoryListResponse(
                memories=[],
                total=0,
                limit=limit,
                offset=offset,
            )

        else:
            # 长期记忆
            ltm = get_long_term_memory()

            # 转换枚举 - 只有当参数是有效字符串时才转换
            mem_type = MemoryType(memory_type) if memory_type and isinstance(memory_type, str) else None
            imp = MemoryImportance(importance) if importance and isinstance(importance, str) else None

            memories = await ltm.search(
                memory_type=mem_type,
                importance=imp,
                agent_id=agent_id,
                session_id=session_id,
                limit=limit,
                offset=offset,
            )

            return MemoryListResponse(
                memories=[
                    MemoryResponse(
                        id=m["memory_id"],
                        memory_id=m.get("memory_id"),
                        content=m.get("content", ""),
                        memory_type=m.get("memory_type"),
                        importance=m.get("importance"),
                        summary=m.get("summary"),
                        tags=m.get("tags", []),
                        metadata=m.get("metadata", {}),
                        agent_id=m.get("agent_id"),
                        session_id=m.get("session_id"),
                        task_id=m.get("task_id"),
                        created_at=m.get("created_at"),
                        updated_at=m.get("updated_at"),
                        access_count=m.get("access_count"),
                    )
                    for m in memories
                ],
                total=len(memories),
                limit=limit,
                offset=offset,
            )

    except Exception as e:
        logger.error("Failed to list memories", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list memories: {str(e)}")


@router.get(
    "/{memory_id}",
    response_model=MemoryResponse,
    summary="获取单个记忆",
    description="根据 ID 获取单个记忆详情",
)
async def get_memory(
    memory_id: str,
    storage: str = Query(default="long_term", description="存储类型"),
):
    """获取单个记忆"""
    try:
        if storage == "short_term":
            memory = get_short_term_memory()
            data = await memory.get(memory_id)

            if not data:
                raise HTTPException(status_code=404, detail="Memory not found")

            return MemoryResponse(
                id=memory_id,
                memory_id=memory_id,
                content=data.get("content", ""),
                memory_type=data.get("memory_type"),
                importance=data.get("importance"),
                tags=data.get("tags", []),
                metadata=data.get("metadata", {}),
                agent_id=data.get("agent_id"),
                session_id=data.get("session_id"),
                task_id=data.get("task_id"),
                created_at=data.get("created_at"),
            )

        elif storage == "vector":
            rag = await get_rag_store()
            data = await rag.get_memory(memory_id)

            if not data:
                raise HTTPException(status_code=404, detail="Memory not found")

            meta = data.get("metadata", {})
            return MemoryResponse(
                id=memory_id,
                memory_id=memory_id,
                content=data.get("content", ""),
                memory_type=meta.get("memory_type"),
                importance=meta.get("importance"),
                tags=meta.get("tags", []),
                metadata=meta,
                agent_id=meta.get("agent_id"),
                session_id=meta.get("session_id"),
                task_id=meta.get("task_id"),
            )

        else:
            ltm = get_long_term_memory()
            data = await ltm.retrieve(memory_id)

            if not data:
                raise HTTPException(status_code=404, detail="Memory not found")

            return MemoryResponse(
                id=memory_id,
                memory_id=data.get("memory_id"),
                content=data.get("content", ""),
                memory_type=data.get("memory_type"),
                importance=data.get("importance"),
                summary=data.get("summary"),
                tags=data.get("tags", []),
                metadata=data.get("metadata", {}),
                agent_id=data.get("agent_id"),
                session_id=data.get("session_id"),
                task_id=data.get("task_id"),
                created_at=data.get("created_at"),
                updated_at=data.get("updated_at"),
                access_count=data.get("access_count"),
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get memory", memory_id=memory_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to get memory: {str(e)}")


@router.delete(
    "/{memory_id}",
    summary="删除记忆",
    description="根据 ID 删除记忆",
)
async def delete_memory(
    memory_id: str,
    storage: str = Query(default="long_term", description="存储类型"),
):
    """删除记忆"""
    try:
        if storage == "short_term":
            memory = get_short_term_memory()
            success = await memory.delete(memory_id)

            if not success:
                raise HTTPException(status_code=404, detail="Memory not found")

            logger.info("Short-term memory deleted", memory_id=memory_id)
            return {"status": "deleted", "memory_id": memory_id}

        elif storage == "vector":
            rag = await get_rag_store()
            success = await rag.delete_memory(memory_id)

            if not success:
                raise HTTPException(status_code=404, detail="Memory not found")

            logger.info("Vector memory deleted", memory_id=memory_id)
            return {"status": "deleted", "memory_id": memory_id}

        else:
            ltm = get_long_term_memory()
            success = await ltm.delete(memory_id)

            if not success:
                raise HTTPException(status_code=404, detail="Memory not found")

            logger.info("Long-term memory deleted", memory_id=memory_id)
            return {"status": "deleted", "memory_id": memory_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete memory", memory_id=memory_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete memory: {str(e)}")


@router.post(
    "/search",
    response_model=MemoryListResponse,
    summary="搜索记忆",
    description="使用查询条件搜索记忆",
)
async def search_memories(request: MemorySearchRequest):
    """搜索记忆"""
    try:
        if request.storage == "short_term":
            # 短期记忆不支持搜索
            return MemoryListResponse(
                memories=[],
                total=0,
                limit=request.limit,
                offset=request.offset,
            )

        elif request.storage == "vector":
            # 向量搜索
            if not request.query:
                raise HTTPException(
                    status_code=400,
                    detail="Query is required for vector search",
                )

            rag = await get_rag_store()
            results = await rag.search(
                query=request.query,
                top_k=request.limit,
            )

            memories = []
            for r in results:
                meta = r.get("metadata", {})
                memories.append(
                    MemoryResponse(
                        id=r.get("memory_id", ""),
                        memory_id=r.get("memory_id"),
                        content=r.get("content", ""),
                        memory_type=meta.get("memory_type"),
                        importance=meta.get("importance"),
                        tags=meta.get("tags", []),
                        metadata=meta,
                        similarity_score=r.get("distance"),
                    )
                )

            return MemoryListResponse(
                memories=memories,
                total=len(memories),
                limit=request.limit,
                offset=request.offset,
            )

        else:
            # 长期记忆搜索
            ltm = get_long_term_memory()

            # 转换枚举
            mem_type = MemoryType(request.memory_type) if request.memory_type else None
            imp = MemoryImportance(request.importance) if request.importance else None

            memories = await ltm.search(
                query=request.query,
                memory_type=mem_type,
                importance=imp,
                tags=request.tags,
                agent_id=request.agent_id,
                session_id=request.session_id,
                task_id=request.task_id,
                limit=request.limit,
                offset=request.offset,
            )

            return MemoryListResponse(
                memories=[
                    MemoryResponse(
                        id=m["memory_id"],
                        memory_id=m.get("memory_id"),
                        content=m.get("content", ""),
                        memory_type=m.get("memory_type"),
                        importance=m.get("importance"),
                        summary=m.get("summary"),
                        tags=m.get("tags", []),
                        metadata=m.get("metadata", {}),
                        agent_id=m.get("agent_id"),
                        session_id=m.get("session_id"),
                        task_id=m.get("task_id"),
                        created_at=m.get("created_at"),
                        updated_at=m.get("updated_at"),
                        access_count=m.get("access_count"),
                    )
                    for m in memories
                ],
                total=len(memories),
                limit=request.limit,
                offset=request.offset,
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to search memories", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to search memories: {str(e)}")


@router.get(
    "/stats/overview",
    response_model=MemoryStatsResponse,
    summary="获取记忆统计",
    description="获取记忆系统的统计信息",
)
async def get_memory_stats(
    storage: str = Query(default="long_term", description="存储类型"),
):
    """获取记忆统计信息"""
    try:
        if storage == "short_term":
            memory = get_short_term_memory()
            stats = await memory.get_stats()

            return MemoryStatsResponse(
                storage_type="short_term",
                total_count=stats.get("total_keys", 0),
            )

        elif storage == "vector":
            rag = await get_rag_store()
            stats = await rag.get_stats()

            return MemoryStatsResponse(
                storage_type="vector",
                total_count=stats.get("total_memories", 0),
            )

        else:
            ltm = get_long_term_memory()
            stats = await ltm.get_stats()

            return MemoryStatsResponse(
                storage_type="long_term",
                total_count=stats.get("total_count", 0),
                by_type=stats.get("by_type"),
                by_importance=stats.get("by_importance"),
                recently_accessed_24h=stats.get("recently_accessed_24h"),
                rag_enabled=stats.get("rag_enabled"),
            )

    except Exception as e:
        logger.error("Failed to get memory stats", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get memory stats: {str(e)}",
        )


@router.get(
    "/important/recent",
    response_model=MemoryListResponse,
    summary="获取重要记忆",
    description="获取高重要性的记忆",
)
async def get_important_memories(
    limit: int = Query(default=10, ge=1, le=100, description="数量限制"),
    agent_id: Optional[str] = Query(None, description="Agent ID 过滤"),
):
    """获取重要记忆"""
    try:
        ltm = get_long_term_memory()
        memories = await ltm.get_important_memories(
            limit=limit,
            agent_id=agent_id,
        )

        return MemoryListResponse(
            memories=[
                MemoryResponse(
                    id=m["memory_id"],
                    memory_id=m.get("memory_id"),
                    content=m.get("content", ""),
                    memory_type=m.get("memory_type"),
                    importance=m.get("importance"),
                    summary=m.get("summary"),
                    tags=m.get("tags", []),
                    metadata=m.get("metadata", {}),
                    agent_id=m.get("agent_id"),
                    session_id=m.get("session_id"),
                    task_id=m.get("task_id"),
                    created_at=m.get("created_at"),
                    updated_at=m.get("updated_at"),
                    access_count=m.get("access_count"),
                )
                for m in memories
            ],
            total=len(memories),
            limit=limit,
            offset=0,
        )

    except Exception as e:
        logger.error("Failed to get important memories", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get important memories: {str(e)}",
        )