"""
Web Fetch 工具

提供安全的 URL 内容获取功能，包含：
- SSRF 防护（强制阻断私网地址）
- 内容提取（readable/raw/markdown）
- 缓存机制
- 重定向安全校验

使用示例:
    web_fetch = WebFetchTool()
    
    # 获取网页内容
    result = await web_fetch(url="https://example.com", extractMode="readable")
    
    # 转换为 Markdown
    result = await web_fetch(url="https://example.com", extractMode="markdown")
"""

import hashlib
import re
import time
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
import structlog
from pydantic import BaseModel, Field, field_validator

from ..base import BaseTool, ToolParameter, ToolResult, ToolStatus
from ..errors import ErrorCode, StandardError
from ..security import SecurityError

logger = structlog.get_logger(__name__)


# =============================================================================
# 请求/响应模型
# =============================================================================


class WebFetchRequest(BaseModel):
    """Web Fetch 请求参数"""

    url: str = Field(..., description="要获取的 URL")
    extract_mode: str = Field(
        default="readable",
        description="内容提取模式: readable | raw | markdown",
    )
    max_chars: int = Field(default=12000, description="最大字符数")
    timeout_ms: int = Field(default=20000, description="超时时间（毫秒）")
    headers: dict[str, str] = Field(default_factory=dict, description="自定义请求头")

    @field_validator("extract_mode")
    @classmethod
    def validate_extract_mode(cls, v: str) -> str:
        allowed = {"readable", "raw", "markdown"}
        if v not in allowed:
            raise ValueError(f"extract_mode must be one of {allowed}")
        return v

    @field_validator("url")
    @classmethod
    def validate_url_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")
        return v.strip()


class WebFetchResponse(BaseModel):
    """Web Fetch 响应数据"""

    url: str = Field(..., description="原始请求 URL")
    final_url: str = Field(..., description="重定向后的最终 URL")
    title: Optional[str] = Field(default=None, description="页面标题")
    content: str = Field(..., description="提取的内容")
    truncated: bool = Field(default=False, description="是否被截断")
    content_type: str = Field(..., description="内容类型")
    status_code: int = Field(..., description="HTTP 状态码")


# =============================================================================
# SSRF 防护模块
# =============================================================================


class SSRFGuard:
    """
    SSRF 防护检查器

    强制阻断对私网地址和危险协议的请求，防止 SSRF 攻击。
    """

    # 私网地址模式
    PRIVATE_PATTERNS = [
        # IPv4 私网地址
        r"^127\.",                    # 回环地址
        r"^10\.",                     # A 类私网
        r"^172\.(1[6-9]|2[0-9]|3[0-1])\.",  # B 类私网
        r"^192\.168\.",               # C 类私网
        r"^169\.254\.",               # 链路本地地址（AWS 元数据）
        r"^0\.0\.0\.0",               # 通配地址

        # IPv6 特殊地址
        r"^::1$",                     # IPv6 回环
        r"^fc00:",                    # IPv6 私网 (Unique Local)
        r"^fe80:",                    # IPv6 链路本地
        r"^::$",                      # IPv6 通配

        # 主机名
        r"^localhost$",
        r"^localhost\.",
        r"\.local$",                  # mDNS
        r"\.localhost$",
        r"\.internal$",               # 内部域名
        r"\.localdomain$",

        # 云元数据服务
        r"^metadata\.",               # 云元数据
        r"^metadata$",                # GCP 元数据
    ]

    # 允许的协议
    ALLOWED_SCHEMES = {"http", "https"}

    # 危险端口
    BLOCKED_PORTS = {
        22,      # SSH
        23,      # Telnet
        25,      # SMTP
        110,     # POP3
        143,     # IMAP
        445,     # SMB
        3306,    # MySQL
        5432,    # PostgreSQL
        6379,    # Redis
        27017,   # MongoDB
        11211,   # Memcached
    }

    def __init__(self, max_chars_cap: int = 20000):
        """
        初始化 SSRF 防护

        Args:
            max_chars_cap: 最大字符数上限
        """
        self.max_chars_cap = max_chars_cap
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.PRIVATE_PATTERNS
        ]

    def validate_url(self, url: str) -> None:
        """
        验证 URL 安全性

        Args:
            url: 待验证的 URL

        Raises:
            SecurityError: URL 不安全时抛出
        """
        # 解析 URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise SecurityError(f"Invalid URL format: {url}") from e

        # 检查协议
        scheme = parsed.scheme.lower()
        if scheme not in self.ALLOWED_SCHEMES:
            raise SecurityError(
                f"URL scheme '{scheme}' is not allowed. "
                f"Only {self.ALLOWED_SCHEMES} are permitted."
            )

        # 检查主机名
        hostname = parsed.hostname
        if not hostname:
            raise SecurityError("URL must contain a valid hostname")

        # 检查私网地址
        self._validate_hostname(hostname)

        # 检查端口
        port = parsed.port
        if port and port in self.BLOCKED_PORTS:
            raise SecurityError(
                f"Port {port} is blocked for security reasons"
            )

    def validate_redirect(self, redirect_url: str) -> None:
        """
        验证重定向 URL 安全性

        对重定向目标执行完整的安全校验。

        Args:
            redirect_url: 重定向目标 URL

        Raises:
            SecurityError: URL 不安全时抛出
        """
        self.validate_url(redirect_url)
        logger.debug(
            "Redirect URL validated",
            redirect_url=redirect_url[:100],
        )

    def _validate_hostname(self, hostname: str) -> None:
        """
        验证主机名是否为私网地址

        Args:
            hostname: 主机名或 IP 地址

        Raises:
            SecurityError: 主机名为私网地址时抛出
        """
        hostname_lower = hostname.lower()

        # 检查所有私网模式
        for pattern in self._compiled_patterns:
            if pattern.search(hostname_lower):
                raise SecurityError(
                    f"Access to private/internal address is blocked: '{hostname}'. "
                    f"SSRF attacks targeting internal resources are not allowed."
                )

        # 额外检查：IP 地址格式变体
        if self._is_potential_private_ip(hostname):
            raise SecurityError(
                f"Access to private IP address is blocked: '{hostname}'"
            )

    def _is_potential_private_ip(self, hostname: str) -> bool:
        """
        检查是否为潜在的私网 IP

        处理各种 IP 格式变体，防止绕过。

        Args:
            hostname: 主机名

        Returns:
            是否为潜在私网 IP
        """
        # 移除可能的端口号
        if ":" in hostname and not hostname.startswith("["):
            hostname = hostname.split(":")[0]

        # 检查十进制格式: 2130706433 = 127.0.0.1
        if hostname.isdigit():
            try:
                ip_num = int(hostname)
                if 0 < ip_num < 4294967296:  # 有效 IPv4 范围
                    ip_parts = [
                        (ip_num >> 24) & 0xFF,
                        (ip_num >> 16) & 0xFF,
                        (ip_num >> 8) & 0xFF,
                        ip_num & 0xFF,
                    ]
                    ip_str = ".".join(map(str, ip_parts))
                    for pattern in self._compiled_patterns[:5]:
                        if pattern.search(ip_str):
                            return True
            except (ValueError, OverflowError):
                pass

        # 检查八进制格式: 0177.0.0.1 = 127.0.0.1
        octal_pattern = r"^0[0-7]+(\.0[0-7]+){0,3}$"
        if re.match(octal_pattern, hostname):
            try:
                parts = [int(p, 8) for p in hostname.split(".") if p]
                if all(0 <= p <= 255 for p in parts):
                    ip_str = ".".join(map(str, parts))
                    for pattern in self._compiled_patterns[:5]:
                        if pattern.search(ip_str):
                            return True
            except (ValueError, IndexError):
                pass

        return False

    def validate_max_chars(self, max_chars: int) -> int:
        """
        验证并限制最大字符数

        Args:
            max_chars: 请求的最大字符数

        Returns:
            安全的最大字符数

        Raises:
            SecurityError: 超过上限时抛出
        """
        if max_chars > self.max_chars_cap:
            raise SecurityError(
                f"max_chars {max_chars} exceeds system cap {self.max_chars_cap}"
            )
        return max_chars


# =============================================================================
# 缓存模块
# =============================================================================


class WebFetchCache:
    """简单的内存缓存"""

    def __init__(self, ttl_seconds: int = 900):  # 默认 15 分钟
        self._cache: dict[str, dict[str, Any]] = {}
        self._ttl = ttl_seconds

    def _get_cache_key(self, url: str, extract_mode: str) -> str:
        """生成缓存键"""
        key_data = f"{url}:{extract_mode}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, url: str, extract_mode: str) -> Optional[WebFetchResponse]:
        """获取缓存"""
        key = self._get_cache_key(url, extract_mode)
        entry = self._cache.get(key)

        if entry:
            if time.time() - entry["timestamp"] < self._ttl:
                logger.debug("Cache hit", url=url[:50])
                return entry["response"]
            else:
                del self._cache[key]

        return None

    def set(self, url: str, extract_mode: str, response: WebFetchResponse) -> None:
        """设置缓存"""
        key = self._get_cache_key(url, extract_mode)
        self._cache[key] = {
            "response": response,
            "timestamp": time.time(),
        }
        logger.debug("Cache set", url=url[:50])

    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        logger.debug("Cache cleared")


# =============================================================================
# 内容提取器
# =============================================================================


class ContentExtractor:
    """内容提取器"""

    @staticmethod
    def extract_title(html: str) -> Optional[str]:
        """提取页面标题"""
        match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if match:
            title = match.group(1).strip()
            title = re.sub(r"\s+", " ", title)
            return title[:200] if len(title) > 200 else title
        return None

    @staticmethod
    def extract_readable(html: str) -> str:
        """
        提取可读内容

        简化实现，移除 HTML 标签并清理。
        """
        # 移除 script 和 style 标签及其内容
        text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<nav[^>]*>.*?</nav>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<footer[^>]*>.*?</footer>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<header[^>]*>.*?</header>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<aside[^>]*>.*?</aside>", "", text, flags=re.IGNORECASE | re.DOTALL)

        # 移除注释
        text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)

        # 移除所有 HTML 标签
        text = re.sub(r"<[^>]+>", " ", text)

        # 处理 HTML 实体
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")

        # 清理多余空白
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)

        return text.strip()

    @staticmethod
    def html_to_markdown(html: str) -> str:
        """
        将 HTML 转换为 Markdown

        简化实现，处理基本的 HTML 元素。
        """
        text = html

        # 移除 script 和 style
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)

        # 标题
        for i in range(6, 0, -1):
            text = re.sub(
                rf"<h{i}[^>]*>(.*?)</h{i}>",
                rf"{'#' * i} \1\n\n",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            )

        # 段落
        text = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", text, flags=re.IGNORECASE | re.DOTALL)

        # 链接
        text = re.sub(
            r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            r"[\2](\1)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )

        # 粗体
        text = re.sub(r"<(strong|b)[^>]*>(.*?)</\1>", r"**\2**", text, flags=re.IGNORECASE | re.DOTALL)

        # 斜体
        text = re.sub(r"<(em|i)[^>]*>(.*?)</\1>", r"*\2*", text, flags=re.IGNORECASE | re.DOTALL)

        # 代码
        text = re.sub(r"<code[^>]*>(.*?)</code>", r"`\1`", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<pre[^>]*>(.*?)</pre>", r"```\n\1\n```", text, flags=re.IGNORECASE | re.DOTALL)

        # 列表
        text = re.sub(r"<li[^>]*>(.*?)</li>", r"- \1\n", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"</?[ou]l[^>]*>", "\n", text, flags=re.IGNORECASE)

        # 换行
        text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
        text = re.sub(r"</div>", "\n", text, flags=re.IGNORECASE)

        # 移除剩余标签
        text = re.sub(r"<[^>]+>", "", text)

        # 处理 HTML 实体
        text = text.replace("&nbsp;", " ")
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#39;", "'")

        # 清理多余空白
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        text = re.sub(r"^\s+", "", text, flags=re.MULTILINE)

        return text.strip()


# =============================================================================
# Web Fetch 工具
# =============================================================================


class WebFetchTool(BaseTool):
    """
    Web Fetch 工具

    提供安全的 URL 内容获取功能。

    安全特性：
    - SSRF 防护：强制阻断私网地址
    - 协议限制：仅允许 HTTP/HTTPS
    - 重定向校验：对重定向目标重新验证
    - 内容大小限制：防止资源耗尽
    """

    NAME = "web_fetch"
    DESCRIPTION = "Fetch and extract content from web URLs securely"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 安全配置
        self.max_chars_cap = kwargs.get("max_chars_cap", 20000)
        self.default_timeout = kwargs.get("default_timeout", 20.0)

        # 初始化 SSRF 防护
        self.ssrf_guard = SSRFGuard(max_chars_cap=self.max_chars_cap)

        # 初始化缓存
        cache_ttl = kwargs.get("cache_ttl_seconds", 900)  # 15 分钟
        self.cache = WebFetchCache(ttl_seconds=cache_ttl)

        # 内容提取器
        self.extractor = ContentExtractor()

        # HTTP 客户端默认配置
        self._default_headers = {
            "User-Agent": "IntelliTeam-WebFetch/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }

    @property
    def parameters(self) -> list[ToolParameter]:
        return [
            ToolParameter(
                name="url",
                description="URL to fetch (HTTP/HTTPS only)",
                type="string",
                required=True,
            ),
            ToolParameter(
                name="extractMode",
                description="Content extraction mode: readable, raw, or markdown",
                type="string",
                required=False,
                default="readable",
                enum=["readable", "raw", "markdown"],
            ),
            ToolParameter(
                name="maxChars",
                description="Maximum characters to return (up to 20000)",
                type="integer",
                required=False,
                default=12000,
            ),
            ToolParameter(
                name="timeoutMs",
                description="Request timeout in milliseconds",
                type="integer",
                required=False,
                default=20000,
            ),
            ToolParameter(
                name="headers",
                description="Custom HTTP headers (JSON object)",
                type="object",
                required=False,
                default={},
            ),
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """执行 Web Fetch"""
        try:
            # 构建请求
            request = self._build_request(kwargs)

            # 安全验证
            self._validate_request(request)

            # 检查缓存
            cached = self.cache.get(request.url, request.extract_mode)
            if cached:
                return ToolResult.ok(
                    data=cached.model_dump(),
                    cached=True,
                )

            # 执行请求
            response = await self._fetch_url(request)

            # 缓存结果
            self.cache.set(request.url, request.extract_mode, response)

            return ToolResult.ok(
                data=response.model_dump(),
                cached=False,
                extract_mode=request.extract_mode,
            )

        except SecurityError as e:
            logger.warning(
                "Web fetch blocked by security",
                url=kwargs.get("url", "")[:100],
                error=str(e),
            )
            return ToolResult.error(
                code=ErrorCode.SECURITY_BLOCKED,
                message=f"Security violation: {e}",
                retryable=False,
                hint="Ensure the URL points to a public internet address",
            )
        except httpx.TimeoutException:
            return ToolResult.error(
                code=ErrorCode.TIMEOUT,
                message="Request timed out",
                retryable=True,
                hint="Try increasing timeoutMs parameter",
            )
        except httpx.HTTPStatusError as e:
            return ToolResult.error(
                code=ErrorCode.DEPENDENCY_ERROR,
                message=f"HTTP error: {e.response.status_code}",
                retryable=e.response.status_code >= 500,
                details={"status_code": e.response.status_code},
            )
        except Exception as e:
            logger.error(
                "Web fetch failed",
                url=kwargs.get("url", "")[:100],
                error=str(e),
            )
            return ToolResult.error(
                code=ErrorCode.INTERNAL_ERROR,
                message=f"Failed to fetch URL: {e}",
                retryable=False,
            )

    def _build_request(self, kwargs: dict[str, Any]) -> WebFetchRequest:
        """构建请求对象"""
        return WebFetchRequest(
            url=kwargs.get("url", ""),
            extract_mode=kwargs.get("extractMode", "readable"),
            max_chars=kwargs.get("maxChars", 12000),
            timeout_ms=kwargs.get("timeoutMs", 20000),
            headers=kwargs.get("headers", {}),
        )

    def _validate_request(self, request: WebFetchRequest) -> None:
        """验证请求安全性"""
        # SSRF 检查
        self.ssrf_guard.validate_url(request.url)

        # 验证 max_chars
        self.ssrf_guard.validate_max_chars(request.max_chars)

    async def _fetch_url(self, request: WebFetchRequest) -> WebFetchResponse:
        """获取 URL 内容"""
        from urllib.parse import urljoin

        original_url = request.url

        # 准备请求头
        headers = dict(self._default_headers)
        headers.update(request.headers)

        # 创建客户端
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(request.timeout_ms / 1000),
            follow_redirects=False,  # 手动处理重定向以验证安全性
            headers=headers,
        ) as client:
            current_url = original_url
            redirect_count = 0
            max_redirects = 5

            while redirect_count <= max_redirects:
                response = await client.get(current_url)

                # 处理重定向
                if response.is_redirect and response.headers.get("location"):
                    redirect_url = response.headers["location"]

                    # 解析相对 URL
                    if not redirect_url.startswith(("http://", "https://")):
                        redirect_url = urljoin(current_url, redirect_url)

                    # 验证重定向 URL
                    self.ssrf_guard.validate_redirect(redirect_url)

                    current_url = redirect_url
                    redirect_count += 1
                    continue

                # 成功获取内容
                break
            else:
                raise Exception(f"Too many redirects (>{max_redirects})")

            final_url = str(response.url)

            # 获取内容类型
            content_type = response.headers.get("content-type", "application/octet-stream")

            # 获取原始内容
            raw_content = response.text

            # 提取内容
            content = self._extract_content(raw_content, request.extract_mode)

            # 提取标题
            title = None
            if "text/html" in content_type:
                title = self.extractor.extract_title(raw_content)

            # 截断处理
            truncated = False
            if len(content) > request.max_chars:
                content = content[:request.max_chars]
                truncated = True

            return WebFetchResponse(
                url=original_url,
                final_url=final_url,
                title=title,
                content=content,
                truncated=truncated,
                content_type=content_type.split(";")[0].strip(),
                status_code=response.status_code,
            )

    def _extract_content(self, html: str, mode: str) -> str:
        """提取内容"""
        if mode == "raw":
            return html
        elif mode == "markdown":
            return self.extractor.html_to_markdown(html)
        else:  # readable
            return self.extractor.extract_readable(html)


# =============================================================================
# 便捷函数
# =============================================================================


async def web_fetch(
    url: str,
    extract_mode: str = "readable",
    max_chars: int = 12000,
    **kwargs,
) -> ToolResult:
    """
    便捷函数：获取网页内容

    Args:
        url: 要获取的 URL
        extract_mode: 提取模式
        max_chars: 最大字符数
        **kwargs: 其他参数

    Returns:
        执行结果
    """
    tool = WebFetchTool()
    return await tool(
        url=url,
        extractMode=extract_mode,
        maxChars=max_chars,
        **kwargs,
    )
