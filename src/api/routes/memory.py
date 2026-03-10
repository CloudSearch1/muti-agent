"""
Memory API 路由

提供完整的记忆系统 CRUD API：
- 短期记忆（Redis）
- 长期记忆（数据库）
- 向量记忆（RAG）

API 端点：
- POST / - 存储记忆
- GET / - 获取记忆列表
- GET /{memory_id} - 获取单个记忆
- DELETE /{memory_id} - 删除记忆
- POST /search - 搜索记忆
- GET /stats/overview - 获取统计信息
- GET /important/recent - 获取重要记忆
"""

from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from src.memory import (
    LongTermMemory,
    MemoryImportance,
    MemoryNotFoundError,
    MemoryType,
    MemoryValidationError,
    RAGStore,
    ShortTermMemory,
    StorageType,
    create_long_term_memory,
    create_rag_store,
    validate_content,
    validate_importance,
    validate_memory_type,
    validate_storage_type,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


# ===========================================
# 请求/响应模型
# ===========================================


class MemoryStoreRequest(BaseModel):
    """存储记忆请求"""

    content: str = Field(..., description="记忆内容", min_length=1, max_length=100000)
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
    summary: str | None = Field(None, description="摘要", max_length=1000)
    tags: list[str] = Field(default_factory=list, description="标签", max_length=20)
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")
    agent_id: str | None = Field(None, description="Agent ID", max_length=64)
    session_id: str | None = Field(None, description="会话 ID", max_length=64)
    task_id: str | None = Field(None, description="任务 ID", max_length=64)
    ttl: int | None = Field(None, description="TTL（秒），仅用于短期记忆", ge=1, le=86400)

    @field_validator("memory_type")
    @classmethod
    def validate_memory_type(cls, v: str) -> str:
        """验证记忆类型"""
        try:
            validate_memory_type(v)
            return v
        except ValueError as e:
            raise ValueError(str(e)) from e

    @field_validator("importance")
    @classmethod
    def validate_importance(cls, v: str) -> str:
        """验证重要性"""
        try:
            validate_importance(v)
            return v
        except ValueError as e:
            raise ValueError(str(e)) from e

    @field_validator("storage")
    @classmethod
    def validate_storage(cls, v: str) -> str:
        """验证存储类型"""
        try:
            validate_storage_type(v)
            return v
        except ValueError as e:
            raise ValueError(str(e)) from e

    @field_validator("content")
    @classmethod
    def validate_content_field(cls, v: str) -> str:
        """验证内容"""
        return validate_content(v)


class MemorySearchRequest(BaseModel):
    """搜索记忆请求"""

    query: str | None = Field(None, description="搜索查询", max_length=1000)
    memory_type: str | None = Field(None, description="记忆类型过滤")
    importance: str | None = Field(None, description="重要性过滤")
    tags: list[str] | None = Field(None, description="标签过滤")
    agent_id: str | None = Field(None, description="Agent ID 过滤")
    session_id: str | None = Field(None, description="会话 ID 过滤")
    task_id: str | None = Field(None, description="任务 ID 过滤")
    storage: str = Field(
        default="long_term",
        description="存储类型: short_term, long_term, vector",
    )
    limit: int = Field(default=10, ge=1, le=100, description="返回数量限制")
    offset: int = Field(default=0, ge=0, description="偏移量")

    @field_validator("memory_type")
    @classmethod
    def validate_memory_type(cls, v: str | None) -> str | None:
        """验证记忆类型"""
        if v is None:
            return None
        try:
            validate_memory_type(v)
            return v
        except ValueError as e:
            raise ValueError(str(e)) from e

    @field_validator("importance")
    @classmethod
    def validate_importance(cls, v: str | None) -> str | None:
        """验证重要性"""
        if v is None:
            return None
        try:
            validate_importance(v)
            return v
        except ValueError as e:
            raise ValueError(str(e)) from e


class MemoryResponse(BaseModel):
    """记忆响应"""

    id: str
    memory_id: str | None = None
    content: str
    memory_type: str | None = None
    importance: str | None = None
    summary: str | None = None
    tags: list[str] = []
    metadata: dict[str, Any] = {}
    agent_id: str | None = None
    session_id: str | None = None
    task_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    access_count: int | None = None
    similarity_score: float | None = None


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
    by_type: dict[str, int] | None = None
    by_importance: dict[str, int] | None = None
    recently_accessed_24h: int | None = None
    rag_enabled: bool | None = None


class DeleteResponse(BaseModel):
    """删除响应"""

    status: str
    memory_id: str


# ===========================================
# 全局实例（延迟初始化）
# ===========================================


_short_term_memory: ShortTermMemory | None = None
_long_term_memory: LongTermMemory | None = None
_rag_store: RAGStore | None = None


def get_short_term_memory() -> ShortTermMemory:
    """获取短期记忆实例（单例）"""
    global _short_term_memory
    if _short_term_memory is None:
        _short_term_memory = ShortTermMemory()
    return _short_term_memory


def get_long_term_memory() -> LongTermMemory:
    """获取长期记忆实例（单例）"""
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = create_long_term_memory()
    return _long_term_memory


async def get_rag_store() -> RAGStore:
    """获取 RAG 存储实例（单例）"""
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
    responses={
        400: {"description": "参数验证失败"},
        500: {"description": "服务器内部错误"},
    },
)
async def store_memory(request: MemoryStoreRequest) -> MemoryResponse:
    """
    存储记忆

    将内容存储到短期记忆（Redis）、长期记忆（数据库）或向量存储（RAG）。

    - **short_term**: 临时存储，支持 TTL 自动过期
    - **long_term**: 持久化存储，支持重要性排序和衰减
    - **vector**: 向量存储，支持语义搜索
    """
    try:
        if request.storage == StorageType.SHORT_TERM.value:
            return await _store_short_term(request)
        elif request.storage == StorageType.VECTOR.value:
            return await _store_vector(request)
        else:
            return await _store_long_term(request)

    except MemoryValidationError as e:
        logger.warning("Validation error", error=str(e), details=e.details)
        raise HTTPException(status_code=400, detail=e.message) from e
    except MemoryNotFoundError as e:
        logger.warning("Memory not found", error=str(e))
        raise HTTPException(status_code=404, detail=e.message) from e
    except Exception as e:
        logger.error("Failed to store memory", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to store memory: {str(e)}") from e


async def _store_short_term(request: MemoryStoreRequest) -> MemoryResponse:
    """存储短期记忆"""
    memory = get_short_term_memory()
    memory_id = f"short_{datetime.now().strftime('%Y%m%d%H%M%S')}_{hash(request.content) % 10000:04d}"

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


async def _store_vector(request: MemoryStoreRequest) -> MemoryResponse:
    """存储向量记忆"""
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


async def _store_long_term(request: MemoryStoreRequest) -> MemoryResponse:
    """存储长期记忆"""
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


@router.get(
    "/",
    response_model=MemoryListResponse,
    summary="获取记忆列表",
    description="获取记忆列表，支持过滤和分页",
)
async def list_memories(
    storage: str = Query(default="long_term", description="存储类型"),
    memory_type: str | None = Query(None, description="记忆类型过滤"),
    importance: str | None = Query(None, description="重要性过滤"),
    agent_id: str | None = Query(None, description="Agent ID 过滤"),
    session_id: str | None = Query(None, description="会话 ID 过滤"),
    limit: int = Query(default=10, ge=1, le=100, description="数量限制"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
) -> MemoryListResponse:
    """获取记忆列表"""
    try:
        # 验证存储类型
        try:
            validate_storage_type(storage)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        if storage == StorageType.SHORT_TERM.value:
            # 短期记忆不支持列表查询
            return MemoryListResponse(memories=[], total=0, limit=limit, offset=offset)

        if storage == StorageType.VECTOR.value:
            # 向量存储返回空列表（需要搜索）
            return MemoryListResponse(memories=[], total=0, limit=limit, offset=offset)

        # 长期记忆
        ltm = get_long_term_memory()

        # 转换枚举
        mem_type = MemoryType(memory_type) if memory_type else None
        imp = MemoryImportance(importance) if importance else None

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

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to list memories", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to list memories: {str(e)}") from e


@router.get(
    "/{memory_id}",
    response_model=MemoryResponse,
    summary="获取单个记忆",
    description="根据 ID 获取单个记忆详情",
    responses={
        404: {"description": "记忆不存在"},
    },
)
async def get_memory(
    memory_id: str,
    storage: str = Query(default="long_term", description="存储类型"),
) -> MemoryResponse:
    """获取单个记忆"""
    try:
        # 验证存储类型
        try:
            validate_storage_type(storage)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        if storage == StorageType.SHORT_TERM.value:
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

        if storage == StorageType.VECTOR.value:
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

        # 长期记忆
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
        raise HTTPException(status_code=500, detail=f"Failed to get memory: {str(e)}") from e


@router.delete(
    "/{memory_id}",
    response_model=DeleteResponse,
    summary="删除记忆",
    description="根据 ID 删除记忆",
    responses={
        404: {"description": "记忆不存在"},
    },
)
async def delete_memory(
    memory_id: str,
    storage: str = Query(default="long_term", description="存储类型"),
) -> DeleteResponse:
    """删除记忆"""
    try:
        # 验证存储类型
        try:
            validate_storage_type(storage)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        if storage == StorageType.SHORT_TERM.value:
            memory = get_short_term_memory()
            success = await memory.delete(memory_id)

            if not success:
                raise HTTPException(status_code=404, detail="Memory not found")

            logger.info("Short-term memory deleted", memory_id=memory_id)
            return DeleteResponse(status="deleted", memory_id=memory_id)

        if storage == StorageType.VECTOR.value:
            rag = await get_rag_store()
            success = await rag.delete_memory(memory_id)

            if not success:
                raise HTTPException(status_code=404, detail="Memory not found")

            logger.info("Vector memory deleted", memory_id=memory_id)
            return DeleteResponse(status="deleted", memory_id=memory_id)

        # 长期记忆
        ltm = get_long_term_memory()
        success = await ltm.delete(memory_id)

        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")

        logger.info("Long-term memory deleted", memory_id=memory_id)
        return DeleteResponse(status="deleted", memory_id=memory_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete memory", memory_id=memory_id, error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to delete memory: {str(e)}") from e


@router.post(
    "/search",
    response_model=MemoryListResponse,
    summary="搜索记忆",
    description="使用查询条件搜索记忆",
)
async def search_memories(request: MemorySearchRequest) -> MemoryListResponse:
    """搜索记忆"""
    try:
        if request.storage == StorageType.SHORT_TERM.value:
            # 短期记忆不支持搜索
            return MemoryListResponse(
                memories=[],
                total=0,
                limit=request.limit,
                offset=request.offset,
            )

        if request.storage == StorageType.VECTOR.value:
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
        raise HTTPException(status_code=500, detail=f"Failed to search memories: {str(e)}") from e


@router.get(
    "/stats/overview",
    response_model=MemoryStatsResponse,
    summary="获取记忆统计",
    description="获取记忆系统的统计信息",
)
async def get_memory_stats(
    storage: str = Query(default="long_term", description="存储类型"),
) -> MemoryStatsResponse:
    """获取记忆统计信息"""
    try:
        # 验证存储类型
        try:
            validate_storage_type(storage)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

        if storage == StorageType.SHORT_TERM.value:
            memory = get_short_term_memory()
            stats = await memory.get_stats()

            return MemoryStatsResponse(
                storage_type="short_term",
                total_count=stats.get("total_keys", 0),
            )

        if storage == StorageType.VECTOR.value:
            rag = await get_rag_store()
            stats = await rag.get_stats()

            return MemoryStatsResponse(
                storage_type="vector",
                total_count=stats.get("total_memories", 0),
            )

        # 长期记忆
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

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get memory stats", error=str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get memory stats: {str(e)}",
        ) from e


@router.get(
    "/important/recent",
    response_model=MemoryListResponse,
    summary="获取重要记忆",
    description="获取高重要性的记忆",
)
async def get_important_memories(
    limit: int = Query(default=10, ge=1, le=100, description="数量限制"),
    agent_id: str | None = Query(None, description="Agent ID 过滤"),
) -> MemoryListResponse:
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
        ) from e
