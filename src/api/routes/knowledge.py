"""
知识库 API 路由

提供知识库管理的 REST API 端点。
"""

import os
import tempfile
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from ...knowledge import (
    ChunkStrategy,
    Document,
    DocumentManager,
    DocumentStatus,
    DocumentType,
    KnowledgeGraph,
    KnowledgeVectorStore,
    QASystem,
    QAResponse,
    RAGEngine,
)
from ...knowledge.exceptions import (
    DocumentNotFoundError,
    DocumentProcessingError,
    KnowledgeError,
)

router = APIRouter(prefix="/knowledge", tags=["Knowledge"])

# 全局实例（实际应用应使用依赖注入）
_document_manager: DocumentManager | None = None
_vector_store: KnowledgeVectorStore | None = None
_qa_system: QASystem | None = None
_knowledge_graph: KnowledgeGraph | None = None


async def get_document_manager() -> DocumentManager:
    """获取文档管理器实例"""
    global _document_manager
    if _document_manager is None:
        _document_manager = DocumentManager()
    return _document_manager


async def get_vector_store() -> KnowledgeVectorStore:
    """获取向量存储实例"""
    global _vector_store
    if _vector_store is None:
        _vector_store = KnowledgeVectorStore()
        await _vector_store.initialize()
    return _vector_store


async def get_qa_system() -> QASystem:
    """获取问答系统实例"""
    global _qa_system
    if _qa_system is None:
        vs = await get_vector_store()
        _qa_system = QASystem(vector_store=vs)
    return _qa_system


async def get_knowledge_graph() -> KnowledgeGraph:
    """获取知识图谱实例"""
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = KnowledgeGraph()
    return _knowledge_graph


# ============ 文档管理 ============


@router.post("/documents", response_model=dict[str, Any], status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    auto_process: bool = Form(True),
):
    """
    上传文档

    - **file**: 文档文件
    - **title**: 文档标题（可选，默认使用文件名）
    - **metadata**: 元数据 JSON 字符串（可选）
    - **auto_process**: 是否自动处理（解析和分块）
    """
    try:
        dm = await get_document_manager()

        # 解析元数据
        meta_dict = {}
        if metadata:
            import json
            try:
                meta_dict = json.loads(metadata)
            except json.JSONDecodeError:
                pass

        # 保存上传的文件到临时位置
        with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        # 上传文档
        doc = await dm.upload_document(
            file=tmp_path,
            filename=title or file.filename,
            metadata=meta_dict,
        )

        # 自动处理
        if auto_process:
            doc = await dm.process_document(doc.id)

            # 添加到向量存储
            if doc.status == DocumentStatus.READY and doc.chunks:
                vs = await get_vector_store()
                await vs.add_document_chunks(
                    document_id=doc.id,
                    chunks=doc.chunks,
                    document_title=doc.title,
                )

        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

        return {
            "success": True,
            "document": doc.to_dict(),
        }

    except KnowledgeError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents", response_model=dict[str, Any])
async def list_documents(
    status: Optional[str] = Query(None),
    doc_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """
    获取文档列表

    - **status**: 状态过滤 (pending, processing, ready, failed)
    - **doc_type**: 类型过滤 (pdf, word, markdown, txt, html)
    - **page**: 页码
    - **page_size**: 每页数量
    """
    try:
        dm = await get_document_manager()

        # 解析过滤条件
        status_filter = DocumentStatus(status) if status else None
        type_filter = DocumentType(doc_type) if doc_type else None

        # 获取文档
        offset = (page - 1) * page_size
        documents = dm.list_documents(
            status=status_filter,
            doc_type=type_filter,
            limit=page_size,
            offset=offset,
        )

        # 统计
        stats = dm.get_stats()

        return {
            "items": [d.to_dict() for d in documents],
            "total": stats["total_documents"],
            "page": page,
            "page_size": page_size,
            "total_pages": (stats["total_documents"] + page_size - 1) // page_size,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{document_id}", response_model=dict[str, Any])
async def get_document(document_id: str):
    """
    获取文档详情

    - **document_id**: 文档 ID
    """
    try:
        dm = await get_document_manager()
        doc = dm.get_document(document_id)

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        return {
            "success": True,
            "document": doc.to_dict(),
            "chunks": [c.to_dict() for c in doc.chunks[:10]],  # 只返回前 10 个分块
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/documents/{document_id}/process", response_model=dict[str, Any])
async def process_document(document_id: str):
    """
    处理文档（解析和分块）

    - **document_id**: 文档 ID
    """
    try:
        dm = await get_document_manager()
        doc = await dm.process_document(document_id)

        # 添加到向量存储
        if doc.status == DocumentStatus.READY and doc.chunks:
            vs = await get_vector_store()
            await vs.add_document_chunks(
                document_id=doc.id,
                chunks=doc.chunks,
                document_title=doc.title,
            )

        return {
            "success": True,
            "document": doc.to_dict(),
        }

    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except DocumentProcessingError as e:
        raise HTTPException(status_code=400, detail=e.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(document_id: str):
    """
    删除文档

    - **document_id**: 文档 ID
    """
    try:
        dm = await get_document_manager()
        vs = await get_vector_store()

        # 从向量存储删除
        await vs.delete_document_chunks(document_id)

        # 删除文档
        await dm.delete_document(document_id)

        return None

    except DocumentNotFoundError:
        raise HTTPException(status_code=404, detail="Document not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 搜索 ============


@router.post("/search", response_model=dict[str, Any])
async def search_knowledge(
    query: str = Query(..., min_length=1),
    top_k: int = Query(5, ge=1, le=50),
    document_id: Optional[str] = Query(None),
    min_score: float = Query(0.0, ge=0.0, le=1.0),
):
    """
    语义搜索

    - **query**: 查询文本
    - **top_k**: 返回结果数量
    - **document_id**: 文档 ID 过滤（可选）
    - **min_score**: 最小相似度分数
    """
    try:
        vs = await get_vector_store()

        # 构建过滤条件
        filters = None
        if document_id:
            filters = {"document_id": document_id}

        # 搜索
        results = await vs.search(
            query=query,
            top_k=top_k,
            filter_metadata=filters,
            min_score=min_score,
        )

        return {
            "success": True,
            "query": query,
            "results": [r.to_dict() for r in results],
            "total": len(results),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 问答 ============


@router.post("/qa", response_model=dict[str, Any])
async def ask_question(
    question: str = Query(..., min_length=1),
    document_id: Optional[str] = Query(None),
    top_k: int = Query(5, ge=1, le=20),
):
    """
    智能问答

    - **question**: 用户问题
    - **document_id**: 文档 ID 过滤（可选）
    - **top_k**: 检索数量
    """
    try:
        qa = await get_qa_system()

        # 构建过滤条件
        filters = None
        if document_id:
            filters = {"document_id": document_id}

        # 回答问题
        response = await qa.answer(
            question=question,
            filters=filters,
            top_k=top_k,
        )

        return {
            "success": True,
            "answer": response.answer,
            "sources": [s.to_dict() for s in response.sources],
            "confidence": response.confidence,
            "query": response.query,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 知识图谱 ============


@router.get("/graph", response_model=dict[str, Any])
async def get_knowledge_graph():
    """
    获取知识图谱数据

    返回节点和边数据，用于前端可视化。
    """
    try:
        kg = await get_knowledge_graph()
        graph_data = kg.get_graph_data()

        return {
            "success": True,
            "graph": graph_data,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/entities/{entity_id}", response_model=dict[str, Any])
async def get_entity(entity_id: str):
    """
    获取实体详情

    - **entity_id**: 实体 ID
    """
    try:
        kg = await get_knowledge_graph()
        entity = kg.get_entity(entity_id)

        if not entity:
            raise HTTPException(status_code=404, detail="Entity not found")

        relations = kg.get_relations_for_entity(entity_id)

        return {
            "success": True,
            "entity": entity.to_dict(),
            "relations": [r.to_dict() for r in relations],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph/entities", response_model=dict[str, Any])
async def search_entities(
    query: str = Query(..., min_length=1),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(10, ge=1, le=50),
):
    """
    搜索实体

    - **query**: 搜索关键词
    - **entity_type**: 实体类型过滤（可选）
    - **limit**: 返回数量限制
    """
    try:
        kg = await get_knowledge_graph()
        entities = kg.search_entities(
            query=query,
            entity_type=entity_type,
            limit=limit,
        )

        return {
            "success": True,
            "entities": [e.to_dict() for e in entities],
            "total": len(entities),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 统计 ============


@router.get("/stats", response_model=dict[str, Any])
async def get_knowledge_stats():
    """
    获取知识库统计信息
    """
    try:
        dm = await get_document_manager()
        vs = await get_vector_store()
        kg = await get_knowledge_graph()

        doc_stats = dm.get_stats()
        vector_stats = await vs.get_stats()
        graph_data = kg.get_graph_data()

        return {
            "success": True,
            "documents": doc_stats,
            "vectors": vector_stats,
            "graph": graph_data["stats"],
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ 配置 ============


@router.get("/config", response_model=dict[str, Any])
async def get_knowledge_config():
    """
    获取知识库配置
    """
    return {
        "supported_types": [t.value for t in DocumentType],
        "chunk_strategies": [s.value for s in ChunkStrategy],
        "document_statuses": [s.value for s in DocumentStatus],
        "entity_types": ["PERSON", "ORGANIZATION", "LOCATION", "DATE", "EVENT", "PRODUCT", "CONCEPT", "TECHNOLOGY"],
        "relation_types": ["WORKS_FOR", "LOCATED_IN", "PART_OF", "RELATED_TO", "CREATED_BY", "USES", "DEVELOPED", "CONTAINS"],
    }