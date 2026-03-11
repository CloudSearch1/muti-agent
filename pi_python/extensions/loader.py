"""
PI-Python 扩展加载器

动态加载 Python 扩展模块
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Callable, Optional

from .api import ExtensionAPI, ExtensionContext


class ExtensionLoader:
    """
    扩展加载器

    支持从文件系统动态加载 Python 扩展
    """

    def __init__(self, extensions_dir: Path):
        """
        初始化扩展加载器

        Args:
            extensions_dir: 扩展目录
        """
        self.extensions_dir = extensions_dir
        self._loaded: dict[str, Any] = {}

    def discover(self) -> list[Path]:
        """发现扩展文件"""
        if not self.extensions_dir.exists():
            return []

        return list(self.extensions_dir.glob("*.py"))

    def load(
        self,
        path: Path,
        api: ExtensionAPI,
        context: Optional[ExtensionContext] = None
    ) -> bool:
        """
        加载扩展

        Args:
            path: 扩展文件路径
            api: 扩展 API
            context: 扩展上下文

        Returns:
            是否加载成功
        """
        name = path.stem

        if name in self._loaded:
            return True

        try:
            # 动态加载模块
            spec = importlib.util.spec_from_file_location(f"extension_{name}", path)
            if not spec or not spec.loader:
                return False

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # 调用扩展入口函数
            entry_points = ["extension", "setup", "init"]

            for entry in entry_points:
                if hasattr(module, entry):
                    func = getattr(module, entry)
                    if callable(func):
                        func(api, context) if context else func(api)
                        break

            self._loaded[name] = module
            return True

        except Exception as e:
            print(f"Failed to load extension {name}: {e}")
            return False

    def load_all(
        self,
        api: ExtensionAPI,
        context: Optional[ExtensionContext] = None
    ) -> int:
        """
        加载所有扩展

        Returns:
            成功加载的扩展数量
        """
        count = 0

        for path in self.discover():
            if self.load(path, api, context):
                count += 1

        return count

    def unload(self, name: str) -> bool:
        """卸载扩展"""
        if name in self._loaded:
            del self._loaded[name]
            return True
        return False

    def is_loaded(self, name: str) -> bool:
        """检查扩展是否已加载"""
        return name in self._loaded

    def list_loaded(self) -> list[str]:
        """列出已加载的扩展"""
        return list(self._loaded.keys())


def create_builtin_extensions() -> dict[str, Callable]:
    """
    创建内置扩展

    Returns:
        内置扩展字典
    """
    extensions = {}

    # 权限控制扩展
    def permission_extension(pi: ExtensionAPI, context=None):
        """权限控制扩展"""
        protected_paths = [".env", "credentials.json", "id_rsa"]

        @pi.on("tool_execution_start")
        async def check_permission(event, ctx):
            if event.tool_name in ("write_file", "edit"):
                path = event.args.get("path", "")
                for protected in protected_paths:
                    if protected in path:
                        # 这里可以调用 UI 确认
                        # 暂时返回警告
                        return {"warning": f"Writing to protected path: {path}"}

    extensions["permission"] = permission_extension

    # 日志扩展
    def logging_extension(pi: ExtensionAPI, context=None):
        """日志扩展"""

        @pi.on("tool_execution_start")
        async def log_tool_start(event, ctx):
            print(f"[Tool] {event.tool_name}({event.args})")

        @pi.on("tool_execution_end")
        async def log_tool_end(event, ctx):
            print(f"[Tool] {event.tool_name} completed")

    extensions["logging"] = logging_extension

    return extensions