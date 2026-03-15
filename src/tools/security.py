"""
工具安全性模块

提供统一的安全检查机制，确保工具执行的安全性。

安全架构:
┌─────────────────────────────────────────────────────────────┐
│                    Security Module                           │
├─────────────────────────────────────────────────────────────┤
│  - SSRF 防护 (URL 验证 + 重定向重检)                         │
│  - 路径安全验证                                              │
│  - 命令注入防护                                              │
│  - AWS/GCP/阿里云元数据端点保护                               │
│  - 同意门禁机制                                              │
│  - 会话隔离                                                  │
│  - 权限校验错误码                                            │
└─────────────────────────────────────────────────────────────┘
"""

import ipaddress
import re
from pathlib import Path
from typing import Any, Dict, Optional, Set, TYPE_CHECKING
from urllib.parse import urlparse

import httpx
import structlog

# 导入标准错误模型
from .errors import (
    ErrorCode,
    StandardError,
    ToolError,
    forbidden_error,
    security_blocked_error,
    unauthorized_error,
)

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from ..memory.session import SessionManager, SessionInfo


class SecurityError(Exception):
    """安全检查失败异常"""

    def __init__(
        self,
        message: str,
        code: ErrorCode = ErrorCode.SECURITY_BLOCKED,
    ):
        super().__init__(message)
        self.code = code
        self.message = message


# ============================================================================
# AWS/GCP/阿里云元数据端点保护
# ============================================================================

AWS_METADATA_PATTERNS = [
    "169.254.169.254",  # AWS IMDSv1/v2
    "metadata.google.internal",  # GCP
    "100.100.100.200",  # Alibaba Cloud
    "metadata.azure.microsoft.com",  # Azure
]

# 私网地址范围
PRIVATE_IP_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),  # Class A 私网
    ipaddress.ip_network("172.16.0.0/12"),  # Class B 私网
    ipaddress.ip_network("192.168.0.0/16"),  # Class C 私网
    ipaddress.ip_network("127.0.0.0/8"),  # 本地回环
    ipaddress.ip_network("169.254.0.0/16"),  # 链路本地
    ipaddress.ip_network("::1/128"),  # IPv6 本地回环
    ipaddress.ip_network("fc00::/7"),  # IPv6 唯一本地地址
    ipaddress.ip_network("fe80::/10"),  # IPv6 链路本地
]


# ============================================================================
# 同意门禁机制
# ============================================================================

class ConsentGate:
    """
    高风险操作的同意门禁

    用于管理需要用户明确同意的高风险操作。

    Example:
        >>> gate = ConsentGate()
        >>> if gate.requires_consent("nodes", "camera"):
        ...     consent = await gate.request_consent("nodes", "camera", context)
        ...     if not consent:
        ...         raise SecurityError("User denied camera access")
    """

    # 高风险操作集合 (tool, action)
    HIGH_RISK_ACTIONS: Set[tuple[str, str]] = {
        # nodes 工具的高风险操作
        ("nodes", "camera"),
        ("nodes", "screen"),
        ("nodes", "run"),
        # gateway 工具的高风险操作
        ("gateway", "config.apply"),
        # exec 工具的提权操作
        ("exec", "elevated"),
        # 浏览器敏感操作
        ("browser", "screenshot"),
        ("browser", "upload"),
    }

    def __init__(self):
        """初始化同意门禁"""
        self._consent_cache: Dict[str, bool] = {}
        self._pending_requests: Dict[str, Any] = {}

    def requires_consent(self, tool: str, action: str) -> bool:
        """
        检查是否需要用户同意

        Args:
            tool: 工具名称
            action: 操作名称

        Returns:
            是否需要用户同意
        """
        return (tool, action) in self.HIGH_RISK_ACTIONS

    async def request_consent(
        self,
        tool: str,
        action: str,
        context: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 60,
    ) -> bool:
        """
        请求用户同意

        Args:
            tool: 工具名称
            action: 操作名称
            context: 操作上下文信息
            timeout_seconds: 等待超时时间（秒）

        Returns:
            用户是否同意
        """
        key = f"{tool}:{action}"

        # 检查缓存
        if key in self._consent_cache:
            return self._consent_cache[key]

        # 生成同意请求
        request = {
            "tool": tool,
            "action": action,
            "context": context or {},
            "timestamp": self._get_timestamp(),
            "timeout": timeout_seconds,
        }

        # 记录等待中的请求
        self._pending_requests[key] = request

        logger.info(
            "Consent requested",
            tool=tool,
            action=action,
            context=context,
        )

        # 在实际实现中，这里会与前端交互
        # 目前返回 False 作为安全默认值
        # 实际使用时需要通过 WebSocket 或其他机制等待用户响应
        logger.warning(
            "Consent gate requires frontend integration",
            tool=tool,
            action=action,
        )

        # 清除等待中的请求
        self._pending_requests.pop(key, None)

        return False

    def grant_consent(self, tool: str, action: str) -> None:
        """
        授予同意（供前端调用）

        Args:
            tool: 工具名称
            action: 操作名称
        """
        key = f"{tool}:{action}"
        self._consent_cache[key] = True
        logger.info("Consent granted", tool=tool, action=action)

    def revoke_consent(self, tool: str, action: str) -> None:
        """
        撤销同意（供前端调用）

        Args:
            tool: 工具名称
            action: 操作名称
        """
        key = f"{tool}:{action}"
        self._consent_cache.pop(key, None)
        logger.info("Consent revoked", tool=tool, action=action)

    def clear_cache(self) -> None:
        """清除所有缓存的同意"""
        self._consent_cache.clear()
        logger.info("Consent cache cleared")

    def _get_timestamp(self) -> str:
        """获取当前时间戳"""
        from datetime import datetime

        return datetime.now().isoformat()


# ============================================================================
# 工具安全检查器
# ============================================================================

class ToolSecurity:
    """
    工具安全检查器

    提供：
    - 路径安全验证
    - 命令注入防护
    - 敏感文件保护
    - SSRF 强制阻断
    - 重定向重检
    - 会话隔离
    - 权限校验错误码
    """

    # 敏感文件模式
    SENSITIVE_PATTERNS = [
        r"\.env$",
        r"\.env\.",
        r"credentials",
        r"secrets?",
        r"\.pem$",
        r"\.key$",
        r"\.p12$",
        r"\.pfx$",
        r"id_rsa",
        r"\.gitconfig",
        r"\.netrc",
        r"\.pgpass",
        r"password",
        r"token",
        r"api_key",
        r"private_key",
    ]

    # 危险命令模式
    DANGEROUS_COMMAND_PATTERNS = [
        r"rm\s+-rf\s+/",
        r"rm\s+-rf\s+~",
        r">\s*/dev/sd",
        r"mkfs",
        r"dd\s+if=",
        r":(){ :\|:& };:",  # Fork bomb
        r"chmod\s+777",
        r"curl.*\|\s*bash",
        r"wget.*\|\s*bash",
        r"eval\s+",
        r"exec\s+",
    ]

    # 允许的文件扩展名
    ALLOWED_EXTENSIONS = {
        "read": {
            ".txt",
            ".py",
            ".js",
            ".ts",
            ".json",
            ".yaml",
            ".yml",
            ".md",
            ".xml",
            ".html",
            ".css",
            ".toml",
            ".ini",
            ".cfg",
        },
        "write": {
            ".py",
            ".js",
            ".ts",
            ".json",
            ".yaml",
            ".yml",
            ".md",
            ".xml",
            ".html",
            ".css",
            ".toml",
            ".txt",
            ".log",
        },
    }

    # 允许的 URL 协议
    ALLOWED_URL_SCHEMES = {"http", "https"}

    def __init__(
        self,
        root_dir: Path | str = ".",
        allow_sensitive: bool = False,
        allow_private: bool = False,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        max_path_length: int = 4096,
        max_redirects: int = 10,
    ):
        """
        初始化安全检查器

        Args:
            root_dir: 根目录，所有操作限制在此目录内
            allow_sensitive: 是否允许访问敏感文件
            allow_private: 是否允许访问私网地址（默认不允许）
            max_file_size: 最大文件大小（字节）
            max_path_length: 最大路径长度
            max_redirects: 最大重定向次数
        """
        self.root_dir = Path(root_dir).resolve()
        self.allow_sensitive = allow_sensitive
        self.allow_private = allow_private
        self.max_file_size = max_file_size
        self.max_path_length = max_path_length
        self.max_redirects = max_redirects

        # 同意门禁实例
        self.consent_gate = ConsentGate()

    # ========================================================================
    # 路径安全验证
    # ========================================================================

    def validate_path(
        self,
        path: str | Path,
        operation: str = "read",
        check_sensitive: bool = True,
    ) -> Path:
        """
        验证路径安全性

        Args:
            path: 待验证的路径
            operation: 操作类型 (read/write)
            check_sensitive: 是否检查敏感文件

        Returns:
            安全的绝对路径

        Raises:
            SecurityError: 路径不安全时抛出
        """
        # 转换为 Path 对象
        if isinstance(path, str):
            path = Path(path)

        # 检查路径长度
        if len(str(path)) > self.max_path_length:
            raise SecurityError(
                f"Path exceeds maximum length: {len(str(path))} > {self.max_path_length}"
            )

        # 解析绝对路径
        try:
            if path.is_absolute():
                full_path = path.resolve()
            else:
                full_path = (self.root_dir / path).resolve()
        except Exception as e:
            raise SecurityError(f"Invalid path: {path}") from e

        # 检查是否在根目录内（防止路径遍历攻击）
        try:
            full_path.relative_to(self.root_dir)
        except ValueError:
            raise SecurityError(
                f"Path '{path}' is outside root directory '{self.root_dir}'"
            ) from None

        # 检查路径中是否包含危险字符
        path_str = str(full_path)
        dangerous_chars = ["..", "~", "$", "`", "|", ";", "&", "<", ">"]
        for char in dangerous_chars:
            if char in path_str:
                raise SecurityError(f"Path contains dangerous character: '{char}'")

        # 检查敏感文件
        if check_sensitive and not self.allow_sensitive:
            self._check_sensitive_file(full_path)

        # 检查文件扩展名
        if operation in self.ALLOWED_EXTENSIONS:
            ext = full_path.suffix.lower()
            allowed = self.ALLOWED_EXTENSIONS[operation]
            if ext and ext not in allowed:
                logger.warning(
                    "Unusual file extension",
                    path=str(full_path),
                    extension=ext,
                    operation=operation,
                )

        return full_path

    # ========================================================================
    # SSRF 强制阻断
    # ========================================================================

    def validate_url(
        self,
        url: str,
        allow_private: bool = False,
    ) -> None:
        """
        验证 URL 安全性（SSRF 强制阻断）

        Args:
            url: 待验证的 URL
            allow_private: 是否允许私网地址（默认使用实例配置）

        Raises:
            SecurityError: URL 不安全时抛出（强制阻断，不再仅警告）
        """
        allow_private = allow_private or self.allow_private

        # 解析 URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise SecurityError(f"Invalid URL format: {url}") from e

        # 检查协议
        scheme = parsed.scheme.lower()
        if scheme and scheme not in self.ALLOWED_URL_SCHEMES:
            raise SecurityError(
                f"URL scheme not allowed: '{scheme}'. "
                f"Allowed schemes: {self.ALLOWED_URL_SCHEMES}"
            )

        hostname = parsed.hostname
        if not hostname:
            raise SecurityError(f"URL has no hostname: {url}")

        # 检查 AWS/GCP/阿里云元数据端点
        for pattern in AWS_METADATA_PATTERNS:
            if hostname.lower() == pattern.lower() or hostname.endswith(f".{pattern}"):
                raise SecurityError(
                    f"Access to cloud metadata endpoint blocked: {hostname}"
                )

        # 检查私网地址（强制阻断）
        if not allow_private:
            self._validate_hostname_not_private(hostname, url)

    def _validate_hostname_not_private(self, hostname: str, url: str) -> None:
        """
        验证主机名不是私网地址

        Args:
            hostname: 主机名
            url: 原始 URL

        Raises:
            SecurityError: 主机名解析为私网地址时抛出
        """
        import socket

        try:
            # 尝试解析主机名
            addr_info = socket.getaddrinfo(hostname, None)
            for family, _, _, _, sockaddr in addr_info:
                ip_str = sockaddr[0]
                try:
                    ip = ipaddress.ip_address(ip_str)
                    # 检查是否在私网范围内
                    for private_range in PRIVATE_IP_RANGES:
                        if ip in private_range:
                            raise SecurityError(
                                f"SSRF blocked: URL '{url}' resolves to "
                                f"private IP address '{ip_str}'. "
                                f"Private network access is not allowed."
                            )
                except ValueError:
                    # 无法解析为 IP，跳过
                    continue

        except socket.gaierror:
            # DNS 解析失败，允许继续（可能是无效域名）
            logger.warning("DNS resolution failed", hostname=hostname)
            return

    # ========================================================================
    # 重定向重检
    # ========================================================================

    async def validate_redirect_chain(
        self,
        url: str,
        client: Optional[httpx.AsyncClient] = None,
    ) -> str:
        """
        验证重定向链中的所有 URL

        发送 HEAD 请求获取重定向链，对每个重定向目标执行 validate_url。

        Args:
            url: 待验证的 URL
            client: 可选的 httpx.AsyncClient 实例

        Returns:
            最终 URL

        Raises:
            SecurityError: 任一重定向目标不安全时抛出
        """
        # 首先验证原始 URL
        self.validate_url(url)

        current_url = url
        redirect_count = 0
        visited_urls: Set[str] = {url}

        # 创建或使用提供的客户端
        should_close_client = False
        if client is None:
            client = httpx.AsyncClient(follow_redirects=False, timeout=10.0)
            should_close_client = True

        try:
            while redirect_count < self.max_redirects:
                try:
                    # 发送 HEAD 请求
                    response = await client.head(current_url, follow_redirects=False)

                    # 检查是否是重定向
                    if response.status_code in (301, 302, 303, 307, 308):
                        redirect_url = response.headers.get("location")
                        if not redirect_url:
                            break

                        # 处理相对 URL
                        if not redirect_url.startswith(("http://", "https://")):
                            from urllib.parse import urljoin

                            redirect_url = urljoin(current_url, redirect_url)

                        # 检测循环重定向
                        if redirect_url in visited_urls:
                            raise SecurityError(
                                f"Redirect loop detected: {redirect_url}"
                            )

                        # 验证重定向目标
                        self.validate_url(redirect_url)

                        visited_urls.add(redirect_url)
                        current_url = redirect_url
                        redirect_count += 1

                        logger.debug(
                            "Redirect followed",
                            from_url=url,
                            to_url=redirect_url,
                            count=redirect_count,
                        )
                    else:
                        # 不是重定向，返回当前 URL
                        break

                except httpx.RequestError as e:
                    logger.warning(
                        "Request error during redirect validation",
                        url=current_url,
                        error=str(e),
                    )
                    break

            if redirect_count >= self.max_redirects:
                raise SecurityError(
                    f"Too many redirects: {redirect_count} > {self.max_redirects}"
                )

            return current_url

        finally:
            if should_close_client:
                await client.aclose()

    # ========================================================================
    # 命令注入防护
    # ========================================================================

    def validate_command(self, command: str | list[str]) -> None:
        """
        验证命令安全性

        Args:
            command: 待执行的命令（字符串或列表）

        Raises:
            SecurityError: 命令不安全时抛出
        """
        if isinstance(command, list):
            command_str = " ".join(command)
        else:
            command_str = command

        # 检查危险命令模式
        for pattern in self.DANGEROUS_COMMAND_PATTERNS:
            if re.search(pattern, command_str, re.IGNORECASE):
                raise SecurityError(f"Dangerous command pattern detected: '{pattern}'")

        # 检查 shell 元字符（如果命令是列表形式）
        if isinstance(command, str):
            shell_chars = ["|", ";", "&", "$", "`", "(", ")", "<", ">", "\n"]
            for char in shell_chars:
                if char in command:
                    logger.warning(
                        "Command contains shell metacharacter",
                        char=char,
                        command=command[:100],
                    )

    # ========================================================================
    # 文件内容验证
    # ========================================================================

    def validate_file_content(
        self,
        content: str,
        max_size: int | None = None,
    ) -> None:
        """
        验证文件内容安全性

        Args:
            content: 文件内容
            max_size: 最大大小（可选）

        Raises:
            SecurityError: 内容不安全时抛出
        """
        max_size = max_size or self.max_file_size

        # 检查大小
        if len(content) > max_size:
            raise SecurityError(
                f"Content exceeds maximum size: {len(content)} > {max_size}"
            )

        # 检查可能的恶意内容
        malicious_patterns = [
            r"<script.*?>.*?</script>",  # XSS
            r"javascript:",  # JavaScript 协议
            r"data:text/html",  # Data URI
        ]

        for pattern in malicious_patterns:
            if re.search(pattern, content, re.IGNORECASE | re.DOTALL):
                logger.warning(
                    "Potentially malicious content detected",
                    pattern=pattern,
                )

    # ========================================================================
    # 会话隔离
    # ========================================================================

    def validate_session_access(
        self,
        session_id: str,
        agent_id: str,
        session_manager: "SessionManager",
    ) -> "SessionInfo":
        """
        验证会话访问权限（同步版本 - 已弃用）

        确保一个 Agent 不能访问其他 Agent 的会话。

        .. deprecated::
            此方法在异步上下文中可能导致问题。
            请使用 `validate_session_access_async` 异步版本替代。

        Args:
            session_id: 会话 ID
            agent_id: 当前 Agent ID
            session_manager: 会话管理器实例

        Returns:
            会话信息

        Raises:
            SecurityError: 访问其他 agent 的会话时抛出
            RuntimeError: 在异步上下文中调用时抛出
        """
        import asyncio

        # 检查是否在异步上下文中
        try:
            loop = asyncio.get_running_loop()
            # 如果能获取到正在运行的 loop，说明在异步上下文中
            raise RuntimeError(
                "validate_session_access cannot be called from an async context. "
                "Use validate_session_access_async instead."
            )
        except RuntimeError as e:
            if "validate_session_access cannot be called" in str(e):
                raise
            # 如果没有正在运行的 loop，说明在同步上下文中，可以安全使用
            loop = asyncio.new_event_loop()
            try:
                session = loop.run_until_complete(
                    session_manager.get_session(session_id)
                )
            finally:
                loop.close()

        if session is None:
            raise SecurityError(f"Session not found: {session_id}")

        # 检查会话所有权
        if session.agent_id != agent_id:
            raise SecurityError(
                f"Cannot access session '{session_id}' owned by another agent "
                f"'{session.agent_id}'. Current agent: '{agent_id}'"
            )

        return session

    async def validate_session_access_async(
        self,
        session_id: str,
        agent_id: str,
        session_manager: "SessionManager",
    ) -> "SessionInfo":
        """
        异步验证会话访问权限

        Args:
            session_id: 会话 ID
            agent_id: 当前 Agent ID
            session_manager: 会话管理器实例

        Returns:
            会话信息

        Raises:
            SecurityError: 访问其他 agent 的会话时抛出
        """
        session = await session_manager.get_session(session_id)

        if session is None:
            raise SecurityError(f"Session not found: {session_id}")

        if session.agent_id != agent_id:
            raise SecurityError(
                f"Cannot access session '{session_id}' owned by another agent "
                f"'{session.agent_id}'. Current agent: '{agent_id}'"
            )

        return session

    # ========================================================================
    # 权限校验错误码
    # ========================================================================

    def raise_unauthorized(self, message: str, **details: Any) -> None:
        """
        抛出未授权错误

        Args:
            message: 错误消息
            **details: 错误详情

        Raises:
            ToolError: UNAUTHORIZED 错误
        """
        raise unauthorized_error(message, **details)

    def raise_forbidden(self, message: str, **details: Any) -> None:
        """
        抛出禁止访问错误

        Args:
            message: 错误消息
            **details: 错误详情

        Raises:
            ToolError: FORBIDDEN 错误
        """
        raise forbidden_error(message, **details)

    def raise_security_blocked(self, message: str, **details: Any) -> None:
        """
        抛出安全阻止错误

        Args:
            message: 错误消息
            **details: 错误详情

        Raises:
            ToolError: SECURITY_BLOCKED 错误
        """
        raise security_blocked_error(message, **details)

    # ========================================================================
    # 内部方法
    # ========================================================================

    def _check_sensitive_file(self, path: Path) -> None:
        """
        检查是否为敏感文件

        Args:
            path: 文件路径

        Raises:
            SecurityError: 文件为敏感文件时抛出
        """
        path_str = str(path).lower()
        filename = path.name.lower()

        for pattern in self.SENSITIVE_PATTERNS:
            if re.search(pattern, path_str) or re.search(pattern, filename):
                raise SecurityError(f"Access to sensitive file denied: '{path.name}'")

    def sanitize_input(self, input_str: str, max_length: int = 10000) -> str:
        """
        清理输入字符串

        Args:
            input_str: 输入字符串
            max_length: 最大长度

        Returns:
            清理后的字符串
        """
        # 截断
        if len(input_str) > max_length:
            input_str = input_str[:max_length]
            logger.warning("Input truncated", original_length=len(input_str))

        # 移除控制字符（保留换行和制表符）
        sanitized = "".join(
            char for char in input_str if char.isprintable() or char in "\n\t\r"
        )

        return sanitized

    def check_resource_limits(self) -> dict[str, Any]:
        """
        检查资源限制

        Returns:
            资源使用情况
        """
        import shutil

        # 磁盘空间
        disk_usage = shutil.disk_usage(self.root_dir)
        disk_percent = (disk_usage.used / disk_usage.total) * 100

        return {
            "disk_total_gb": disk_usage.total / (1024**3),
            "disk_used_gb": disk_usage.used / (1024**3),
            "disk_free_gb": disk_usage.free / (1024**3),
            "disk_percent": round(disk_percent, 2),
            "root_dir": str(self.root_dir),
            "healthy": disk_percent < 90,
        }


# ============================================================================
# 全局安全检查器实例
# ============================================================================

_security_checker: ToolSecurity | None = None


def get_security_checker(root_dir: Path | str = ".") -> ToolSecurity:
    """获取全局安全检查器"""
    global _security_checker
    if _security_checker is None:
        _security_checker = ToolSecurity(root_dir=root_dir)
    return _security_checker


def validate_path_safety(
    path: str | Path,
    root_dir: Path | str = ".",
    operation: str = "read",
) -> Path:
    """
    便捷函数：验证路径安全性

    Args:
        path: 待验证的路径
        root_dir: 根目录
        operation: 操作类型

    Returns:
        安全的绝对路径
    """
    checker = get_security_checker(root_dir)
    return checker.validate_path(path, operation)


def validate_command_safety(command: str | list[str]) -> None:
    """
    便捷函数：验证命令安全性

    Args:
        command: 待执行的命令
    """
    checker = get_security_checker()
    checker.validate_command(command)


def validate_url_safety(url: str, allow_private: bool = False) -> None:
    """
    便捷函数：验证 URL 安全性

    Args:
        url: 待验证的 URL
        allow_private: 是否允许私网地址
    """
    checker = get_security_checker()
    checker.validate_url(url, allow_private)


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    # 错误类型（从 errors 模块重新导出）
    "ErrorCode",
    "StandardError",
    "ToolError",
    # 安全错误
    "SecurityError",
    # 元数据保护
    "AWS_METADATA_PATTERNS",
    # 同意门禁
    "ConsentGate",
    # 安全检查器
    "ToolSecurity",
    # 便捷函数
    "get_security_checker",
    "validate_path_safety",
    "validate_command_safety",
    "validate_url_safety",
]
