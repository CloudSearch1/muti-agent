"""
工具安全性模块

提供统一的安全检查机制，确保工具执行的安全性。
"""

import re
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SecurityError(Exception):
    """安全检查失败异常"""
    pass


class ToolSecurity:
    """
    工具安全检查器

    提供：
    - 路径安全验证
    - 命令注入防护
    - 敏感文件保护
    - 资源限制检查
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
        "read": {".txt", ".py", ".js", ".ts", ".json", ".yaml", ".yml", ".md", ".xml", ".html", ".css", ".toml", ".ini", ".cfg"},
        "write": {".py", ".js", ".ts", ".json", ".yaml", ".yml", ".md", ".xml", ".html", ".css", ".toml", ".txt", ".log"},
    }

    def __init__(
        self,
        root_dir: Path | str = ".",
        allow_sensitive: bool = False,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        max_path_length: int = 4096,
    ):
        """
        初始化安全检查器

        Args:
            root_dir: 根目录，所有操作限制在此目录内
            allow_sensitive: 是否允许访问敏感文件
            max_file_size: 最大文件大小（字节）
            max_path_length: 最大路径长度
        """
        self.root_dir = Path(root_dir).resolve()
        self.allow_sensitive = allow_sensitive
        self.max_file_size = max_file_size
        self.max_path_length = max_path_length

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
            raise SecurityError(f"Path exceeds maximum length: {len(str(path))} > {self.max_path_length}")

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

    def validate_url(self, url: str) -> None:
        """
        验证 URL 安全性

        Args:
            url: 待验证的 URL

        Raises:
            SecurityError: URL 不安全时抛出
        """
        # 检查协议
        allowed_schemes = ["http", "https"]
        scheme = url.split("://")[0].lower() if "://" in url else ""

        if scheme and scheme not in allowed_schemes:
            raise SecurityError(f"URL scheme not allowed: '{scheme}'")

        # 检查内网地址（可选）
        internal_patterns = [
            r"localhost",
            r"127\.",
            r"10\.",
            r"172\.(1[6-9]|2[0-9]|3[0-1])\.",
            r"192\.168\.",
        ]

        for pattern in internal_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                logger.warning(
                    "URL points to internal address",
                    url=url[:100],
                )
                # 不阻止，但记录警告

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
                raise SecurityError(
                    f"Access to sensitive file denied: '{path.name}'"
                )

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
            char for char in input_str
            if char.isprintable() or char in "\n\t\r"
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
            "disk_total_gb": disk_usage.total / (1024 ** 3),
            "disk_used_gb": disk_usage.used / (1024 ** 3),
            "disk_free_gb": disk_usage.free / (1024 ** 3),
            "disk_percent": round(disk_percent, 2),
            "root_dir": str(self.root_dir),
            "healthy": disk_percent < 90,
        }


# 全局安全检查器实例
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
