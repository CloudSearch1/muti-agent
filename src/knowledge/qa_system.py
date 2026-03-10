"""
问答系统模块

提供基于 RAG 的智能问答功能。
"""

from typing import Any

import structlog

from ..llm.llm_provider import BaseProvider, get_llm
from .exceptions import QASystemError
from .rag_engine import RAGEngine
from .types import QAResponse, SearchResult
from .vector_store import KnowledgeVectorStore

logger = structlog.get_logger(__name__)

# 默认配置
DEFAULT_TOP_K = 5
DEFAULT_MAX_CONTEXT_TOKENS = 3000
DEFAULT_MIN_SCORE = 0.3
DEFAULT_TEMPERATURE = 0.7

# 提示词模板
SYSTEM_PROMPT = """你是一个专业的知识库问答助手。你的任务是基于提供的上下文信息，准确、专业地回答用户的问题。

要求：
1. 回答必须基于上下文信息，不要编造或使用外部知识
2. 如果上下文中没有相关信息，请明确告知用户
3. 回答要简洁明了，重点突出
4. 适当引用来源（如[来源1]）
5. 如果问题涉及多个方面，请分点回答"""

QA_PROMPT_TEMPLATE = """## 上下文信息
{context}

## 用户问题
{question}

## 回答
请基于以上上下文信息，回答用户的问题。如果上下文中没有相关信息，请明确说明。"""


class QASystem:
    """
    问答系统

    基于 RAG 的智能问答系统。

    Example:
        >>> qa = QASystem(vector_store)
        >>> response = await qa.answer("什么是 RAG?")
        >>> print(response.answer)
    """

    def __init__(
        self,
        vector_store: KnowledgeVectorStore,
        llm_provider: BaseProvider | None = None,
        top_k: int = DEFAULT_TOP_K,
        max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS,
        min_score: float = DEFAULT_MIN_SCORE,
        temperature: float = DEFAULT_TEMPERATURE,
    ) -> None:
        """
        初始化问答系统

        Args:
            vector_store: 向量存储
            llm_provider: LLM 提供者
            top_k: 检索数量
            max_context_tokens: 最大上下文 token
            min_score: 最小相似度分数
            temperature: 生成温度
        """
        self.vector_store = vector_store
        self.llm_provider = llm_provider or get_llm()
        self.top_k = top_k
        self.max_context_tokens = max_context_tokens
        self.min_score = min_score
        self.temperature = temperature

        # RAG 引擎
        self._rag_engine = RAGEngine(
            vector_store=vector_store,
            llm_provider=llm_provider,
            top_k=top_k,
            max_context_tokens=max_context_tokens,
            min_score=min_score,
        )

        self.logger = logger.bind(component="qa_system")

    async def answer(
        self,
        question: str,
        filters: dict[str, Any] | None = None,
        top_k: int | None = None,
    ) -> QAResponse:
        """
        回答问题

        Args:
            question: 用户问题
            filters: 过滤条件
            top_k: 检索数量

        Returns:
            问答响应

        Raises:
            QASystemError: 问答失败
        """
        if not question or not question.strip():
            return QAResponse(
                answer="请提供有效的问题。",
                sources=[],
                confidence=0.0,
                query=question or "",
            )

        try:
            # 检索相关文档
            results = await self._rag_engine.retrieve(
                query=question,
                top_k=top_k or self.top_k,
                filters=filters,
                min_score=self.min_score,
            )

            # 如果没有找到相关文档
            if not results:
                return QAResponse(
                    answer="抱歉，我在知识库中没有找到与您问题相关的信息。请尝试换一种方式提问，或者联系管理员添加相关文档。",
                    sources=[],
                    confidence=0.0,
                    query=question,
                )

            # 构建上下文
            context = self._rag_engine.build_context(
                results=results,
                max_tokens=self.max_context_tokens,
                include_metadata=True,
            )

            # 生成回答
            prompt = QA_PROMPT_TEMPLATE.format(
                context=context,
                question=question,
            )

            answer_text = await self.llm_provider.generate(
                prompt=prompt,
                temperature=self.temperature,
                max_tokens=1000,
            )

            # 计算置信度
            confidence = self._calculate_confidence(results)

            # 获取来源
            sources = results[:3]  # 最多返回 3 个来源

            self.logger.info(
                "Question answered",
                question=question[:50],
                sources_count=len(sources),
                confidence=confidence,
            )

            return QAResponse(
                answer=answer_text,
                sources=sources,
                confidence=confidence,
                query=question,
            )

        except Exception as e:
            self.logger.error("Failed to answer question", error=str(e))
            raise QASystemError(
                f"Failed to answer question: {e}",
                query=question,
            ) from e

    async def answer_with_sources(
        self,
        question: str,
        filters: dict[str, Any] | None = None,
        top_k: int | None = None,
    ) -> QAResponse:
        """
        带来源的回答

        与 answer() 相同，但确保返回来源信息。

        Args:
            question: 用户问题
            filters: 过滤条件
            top_k: 检索数量

        Returns:
            问答响应（包含来源）
        """
        return await self.answer(question, filters, top_k)

    async def stream_answer(
        self,
        question: str,
        filters: dict[str, Any] | None = None,
        top_k: int | None = None,
    ):
        """
        流式回答

        Args:
            question: 用户问题
            filters: 过滤条件
            top_k: 检索数量

        Yields:
            回答片段
        """
        if not question or not question.strip():
            yield "请提供有效的问题。"
            return

        try:
            # 检索
            results = await self._rag_engine.retrieve(
                query=question,
                top_k=top_k or self.top_k,
                filters=filters,
                min_score=self.min_score,
            )

            if not results:
                yield "抱歉，我在知识库中没有找到与您问题相关的信息。"
                return

            # 构建上下文
            context = self._rag_engine.build_context(
                results=results,
                max_tokens=self.max_context_tokens,
            )

            # 流式生成
            prompt = QA_PROMPT_TEMPLATE.format(
                context=context,
                question=question,
            )

            async for chunk in self.llm_provider.generate_stream(
                prompt=prompt,
                temperature=self.temperature,
                max_tokens=1000,
            ):
                yield chunk

        except Exception as e:
            self.logger.error("Stream answer failed", error=str(e))
            yield f"回答生成失败: {e}"

    def _calculate_confidence(self, results: list[SearchResult]) -> float:
        """
        计算置信度

        基于检索结果的分数和数量计算置信度。

        Args:
            results: 检索结果

        Returns:
            置信度（0-1）
        """
        if not results:
            return 0.0

        # 计算平均分数
        avg_score = sum(r.score for r in results) / len(results)

        # 考虑结果数量（越多越可信，但有上限）
        count_factor = min(len(results) / 5, 1.0)

        # 综合置信度
        confidence = avg_score * 0.7 + count_factor * 0.3

        return min(max(confidence, 0.0), 1.0)

    async def suggest_questions(
        self,
        document_id: str | None = None,
        count: int = 5,
    ) -> list[str]:
        """
        生成推荐问题

        Args:
            document_id: 文档 ID（可选）
            count: 推荐数量

        Returns:
            推荐问题列表
        """
        try:
            # 获取一些文档内容
            if document_id:
                results = await self.vector_store.search(
                    query="",
                    top_k=3,
                    filter_metadata={"document_id": document_id},
                )
            else:
                # 随机获取一些内容
                results = await self.vector_store.search(
                    query="知识",
                    top_k=3,
                )

            if not results:
                return []

            # 构建提示
            content = "\n".join(r.content[:300] for r in results[:3])

            prompt = f"""基于以下内容，生成 {count} 个用户可能会问的问题：

内容:
{content}

要求：
1. 问题要具体、有针对性
2. 问题要有实际意义
3. 每行一个问题，不要编号

问题:"""

            response = await self.llm_provider.generate(
                prompt=prompt,
                temperature=0.8,
                max_tokens=300,
            )

            # 解析问题
            questions = [
                q.strip()
                for q in response.strip().split("\n")
                if q.strip() and not q.strip().startswith("#")
            ]

            return questions[:count]

        except Exception as e:
            self.logger.warning("Failed to suggest questions", error=str(e))
            return []
