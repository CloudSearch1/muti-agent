"""
网络搜索工具

提供网络搜索功能，支持多种搜索引擎后端。
包含缓存机制和结果标准化。

架构:
┌─────────────────────────────────────────────────────────────┐
│                       WebSearchTool                          │
│  - 参数验证                                                  │
│  - 缓存管理                                                  │
│  - 结果标准化                                                │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     SearchBackend (ABC)                      │
│  - 搜索引擎抽象接口                                          │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   DuckDuckGoBackend    BingBackend          GoogleBackend
   (无需 API Key)       (需要 API Key)       (需要 API Key)
"""

import hashlib
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

import structlog
from pydantic import BaseModel, Field

from ..base import BaseTool, ToolParameter, ToolResult
from ..errors import ErrorCode, ToolError

logger = structlog.get_logger(__name__)


# ============================================================================
# 数据模型
# ============================================================================


class WebSearchRequest(BaseModel):
    """网络搜索请求参数"""

    query: str = Field(..., description="搜索查询字符串")
    count: int = Field(default=5, ge=1, le=10, description="结果数量，范围 1-10")
    locale: str = Field(default="zh-CN", description="语言区域设置")
    safe_search: str = Field(
        default="moderate",
        description="安全搜索级别: off | moderate | strict",
    )
    freshness_days: Optional[int] = Field(
        default=7,
        description="时效性天数，限制结果在指定天数内发布",
    )


class WebSearchResult(BaseModel):
    """单条搜索结果"""

    title: str = Field(..., description="结果标题")
    url: str = Field(..., description="结果链接")
    snippet: str = Field(default="", description="结果摘要")
    source: str = Field(..., description="搜索引擎来源")
    published_at: Optional[datetime] = Field(
        default=None,
        description="发布时间",
    )


class CacheInfo(BaseModel):
    """缓存信息"""

    hit: bool = Field(default=False, description="是否命中缓存")
    ttl_sec: int = Field(default=900, description="缓存有效期（秒）")


class WebSearchResponse(BaseModel):
    """网络搜索响应"""

    results: list[WebSearchResult] = Field(
        default_factory=list,
        description="搜索结果列表",
    )
    cache: CacheInfo = Field(
        default_factory=lambda: CacheInfo(),
        description="缓存信息",
    )


# ============================================================================
# 缓存机制
# ============================================================================


class SearchCache:
    """
    搜索结果缓存

    使用内存缓存存储搜索结果，支持 TTL 过期。
    """

    def __init__(self, ttl_sec: int = 900):
        """
        初始化缓存

        Args:
            ttl_sec: 缓存有效期（秒），默认 15 分钟
        """
        self._cache: dict[str, tuple[list[WebSearchResult], float]] = {}
        self._ttl = ttl_sec

    def _make_cache_key(
        self,
        query: str,
        params: dict[str, Any],
    ) -> str:
        """
        生成缓存键

        Args:
            query: 搜索查询
            params: 搜索参数

        Returns:
            缓存键（MD5 哈希）
        """
        # 将查询和参数组合成字符串
        key_parts = [query]
        for k in sorted(params.keys()):
            key_parts.append(f"{k}={params[k]}")
        key_str = "|".join(key_parts)

        # 生成 MD5 哈希
        return hashlib.md5(key_str.encode()).hexdigest()

    def get(
        self,
        query: str,
        params: dict[str, Any],
    ) -> Optional[list[WebSearchResult]]:
        """
        获取缓存结果

        Args:
            query: 搜索查询
            params: 搜索参数

        Returns:
            缓存结果，不存在或已过期返回 None
        """
        cache_key = self._make_cache_key(query, params)

        if cache_key not in self._cache:
            return None

        results, timestamp = self._cache[cache_key]

        # 检查是否过期
        if time.time() - timestamp > self._ttl:
            del self._cache[cache_key]
            return None

        logger.debug(
            "Cache hit",
            cache_key=cache_key,
            results_count=len(results),
        )

        return results

    def set(
        self,
        query: str,
        params: dict[str, Any],
        results: list[WebSearchResult],
    ) -> None:
        """
        设置缓存结果

        Args:
            query: 搜索查询
            params: 搜索参数
            results: 搜索结果
        """
        cache_key = self._make_cache_key(query, params)
        self._cache[cache_key] = (results, time.time())

        logger.debug(
            "Cache set",
            cache_key=cache_key,
            results_count=len(results),
            ttl_sec=self._ttl,
        )

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logger.info("Cache cleared")

    def cleanup_expired(self) -> int:
        """
        清理过期缓存

        Returns:
            清理的缓存条目数
        """
        current_time = time.time()
        expired_keys = [
            key
            for key, (_, timestamp) in self._cache.items()
            if current_time - timestamp > self._ttl
        ]

        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.info(
                "Cleaned up expired cache entries",
                count=len(expired_keys),
            )

        return len(expired_keys)


# ============================================================================
# 搜索引擎后端
# ============================================================================


class SearchBackend(ABC):
    """搜索引擎后端抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """搜索引擎名称"""
        pass

    @abstractmethod
    async def search(
        self,
        request: WebSearchRequest,
    ) -> list[WebSearchResult]:
        """
        执行搜索

        Args:
            request: 搜索请求

        Returns:
            搜索结果列表
        """
        pass


class DuckDuckGoBackend(SearchBackend):
    """
    DuckDuckGo 搜索后端

    使用 duckduckgo-search 库，无需 API Key。
    """

    def __init__(self, **kwargs):
        """初始化 DuckDuckGo 后端"""
        self._client = None

    @property
    def name(self) -> str:
        return "duckduckgo"

    async def _get_client(self):
        """懒加载 DuckDuckGo 客户端"""
        if self._client is None:
            try:
                from duckduckgo_search import DDGS

                self._client = DDGS()
            except ImportError:
                raise ToolError(
                    code=ErrorCode.DEPENDENCY_ERROR,
                    message="duckduckgo-search 库未安装",
                    retryable=False,
                    hint="请运行: pip install duckduckgo-search",
                )
        return self._client

    async def search(
        self,
        request: WebSearchRequest,
    ) -> list[WebSearchResult]:
        """执行 DuckDuckGo 搜索"""
        try:
            client = await self._get_client()

            # 构建搜索参数
            search_kwargs = {
                "keywords": request.query,
                "max_results": request.count,
            }

            # 添加区域设置
            if request.locale:
                search_kwargs["region"] = request.locale

            # 添加安全搜索
            safe_search_map = {
                "off": "off",
                "moderate": "moderate",
                "strict": "strict",
            }
            search_kwargs["safesearch"] = safe_search_map.get(
                request.safe_search,
                "moderate",
            )

            # 添加时效性
            if request.freshness_days:
                search_kwargs["timelimit"] = f"d{request.freshness_days}"

            # 执行搜索
            results = []
            search_results = client.text(**search_kwargs)

            for item in search_results:
                result = WebSearchResult(
                    title=item.get("title", ""),
                    url=item.get("href", ""),
                    snippet=item.get("body", ""),
                    source=self.name,
                    published_at=None,  # DuckDuckGo 不提供发布时间
                )
                results.append(result)

            logger.info(
                "DuckDuckGo search completed",
                query=request.query,
                results_count=len(results),
            )

            return results

        except ToolError:
            raise
        except Exception as e:
            logger.error(
                "DuckDuckGo search failed",
                query=request.query,
                error=str(e),
            )
            raise ToolError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"DuckDuckGo 搜索失败: {str(e)}",
                retryable=True,
                details={"query": request.query},
            )


class BingBackend(SearchBackend):
    """
    Bing 搜索后端

    使用 Bing Web Search API，需要 API Key。
    """

    def __init__(self, api_key: str, **kwargs):
        """
        初始化 Bing 后端

        Args:
            api_key: Bing API Key
        """
        self._api_key = api_key
        self._endpoint = "https://api.bing.microsoft.com/v7.0/search"

    @property
    def name(self) -> str:
        return "bing"

    async def search(
        self,
        request: WebSearchRequest,
    ) -> list[WebSearchResult]:
        """执行 Bing 搜索"""
        try:
            import httpx

            # 构建请求参数
            params = {
                "q": request.query,
                "count": request.count,
                "mkt": request.locale,
                "safeSearch": request.safe_search,
            }

            if request.freshness_days:
                params["freshness"] = f"Day{request.freshness_days}"

            headers = {
                "Ocp-Apim-Subscription-Key": self._api_key,
            }

            # 发送请求
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self._endpoint,
                    params=params,
                    headers=headers,
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()

            # 解析结果
            results = []
            web_pages = data.get("webPages", {}).get("value", [])

            for item in web_pages:
                result = WebSearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    source=self.name,
                    published_at=item.get("dateLastCrawled"),
                )
                results.append(result)

            logger.info(
                "Bing search completed",
                query=request.query,
                results_count=len(results),
            )

            return results

        except Exception as e:
            logger.error(
                "Bing search failed",
                query=request.query,
                error=str(e),
            )
            raise ToolError(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Bing 搜索失败: {str(e)}",
                retryable=True,
                details={"query": request.query},
            )


# ============================================================================
# WebSearchTool 工具类
# ============================================================================


class WebSearchTool(BaseTool):
    """
    网络搜索工具

    提供网络搜索功能，支持多种搜索引擎后端。
    默认使用 DuckDuckGo（无需 API Key）。

    功能特性：
    - 多搜索引擎支持
    - 结果缓存
    - 安全搜索
    - 时效性过滤
    """

    NAME = "web_search"
    DESCRIPTION = "网络搜索工具，用于搜索互联网上的信息"

    def __init__(
        self,
        backend: Optional[SearchBackend] = None,
        cache_ttl: int = 900,
        **kwargs,
    ):
        """
        初始化网络搜索工具

        Args:
            backend: 搜索引擎后端，默认使用 DuckDuckGo
            cache_ttl: 缓存有效期（秒），默认 15 分钟
            **kwargs: 其他配置参数
        """
        super().__init__(**kwargs)

        # 默认使用 DuckDuckGo 后端
        self.backend = backend or DuckDuckGoBackend()
        self.cache = SearchCache(ttl_sec=cache_ttl)

        # 配置参数
        self.default_count = kwargs.get("default_count", 5)
        self.default_locale = kwargs.get("default_locale", "zh-CN")
        self.default_safe_search = kwargs.get("default_safe_search", "moderate")

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="action",
                description="操作类型",
                type="string",
                required=True,
                enum=["run"],
                default="run",
            ),
            ToolParameter(
                name="query",
                description="搜索查询字符串",
                type="string",
                required=True,
            ),
            ToolParameter(
                name="count",
                description="结果数量，范围 1-10",
                type="integer",
                required=False,
                default=5,
            ),
            ToolParameter(
                name="locale",
                description="语言区域设置",
                type="string",
                required=False,
                default="zh-CN",
            ),
            ToolParameter(
                name="safeSearch",
                description="安全搜索级别: off | moderate | strict",
                type="string",
                required=False,
                default="moderate",
                enum=["off", "moderate", "strict"],
            ),
            ToolParameter(
                name="freshnessDays",
                description="时效性天数，限制结果在指定天数内发布",
                type="integer",
                required=False,
                default=7,
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """执行网络搜索"""
        action = kwargs.get("action", "run")

        if action != "run":
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message=f"未知的操作类型: {action}",
                details={"action": action},
            )

        # 构建搜索请求
        query = kwargs.get("query", "")
        if not query:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message="搜索查询不能为空",
                hint="请提供 query 参数",
            )

        # 清理查询字符串
        query = query.strip()

        # 构建搜索参数
        search_params = {
            "count": kwargs.get("count", self.default_count),
            "locale": kwargs.get("locale", self.default_locale),
            "safe_search": kwargs.get("safeSearch", self.default_safe_search),
            "freshness_days": kwargs.get("freshnessDays", 7),
        }

        # 参数验证
        count = search_params["count"]
        if not isinstance(count, int) or count < 1 or count > 10:
            return ToolResult.error(
                code=ErrorCode.VALIDATION_ERROR,
                message="结果数量必须在 1-10 之间",
                details={"count": count},
                hint="count 参数必须是 1 到 10 之间的整数",
            )

        # 检查缓存
        cached_results = self.cache.get(query, search_params)
        if cached_results is not None:
            response = WebSearchResponse(
                results=cached_results,
                cache=CacheInfo(hit=True, ttl_sec=self.cache._ttl),
            )

            return ToolResult.ok(
                data=response.model_dump(),
                query=query,
                cached=True,
            )

        # 执行搜索
        try:
            request = WebSearchRequest(
                query=query,
                **search_params,
            )

            results = await self.backend.search(request)

            # 缓存结果
            self.cache.set(query, search_params, results)

            # 构建响应
            response = WebSearchResponse(
                results=results,
                cache=CacheInfo(hit=False, ttl_sec=self.cache._ttl),
            )

            return ToolResult.ok(
                data=response.model_dump(),
                query=query,
                backend=self.backend.name,
                results_count=len(results),
            )

        except ToolError as e:
            self.logger.error(
                "Web search failed",
                query=query,
                error=str(e),
            )
            return ToolResult(
                status="error",
                error=e.error,
                query=query,
            )
        except Exception as e:
            self.logger.error(
                "Web search failed",
                query=query,
                error=str(e),
            )
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"搜索失败: {str(e)}",
                retryable=True,
                details={"query": query},
            )


# ============================================================================
# 便捷函数
# ============================================================================


async def web_search(
    query: str,
    count: int = 5,
    locale: str = "zh-CN",
    safe_search: str = "moderate",
    freshness_days: Optional[int] = 7,
    backend: Optional[SearchBackend] = None,
) -> WebSearchResponse:
    """
    便捷函数：执行网络搜索

    Args:
        query: 搜索查询
        count: 结果数量，范围 1-10
        locale: 语言区域
        safe_search: 安全搜索级别
        freshness_days: 时效性天数
        backend: 搜索引擎后端

    Returns:
        搜索响应
    """
    tool = WebSearchTool(backend=backend)

    result = await tool(
        action="run",
        query=query,
        count=count,
        locale=locale,
        safeSearch=safe_search,
        freshnessDays=freshness_days,
    )

    if result.is_ok():
        return WebSearchResponse(**result.data)
    else:
        raise RuntimeError(result.error.message if result.error else "Unknown error")
