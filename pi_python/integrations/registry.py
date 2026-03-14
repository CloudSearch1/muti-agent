"""
PI-Python 集成注册表

管理所有已注册的平台集成
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import BaseIntegration


class IntegrationRegistry:
    """集成注册表"""
    
    def __init__(self):
        self._integrations: dict[str, BaseIntegration] = {}
    
    def register(self, name: str, integration: BaseIntegration) -> None:
        """
        注册集成
        
        Args:
            name: 集成名称
            integration: 集成实例
        """
        self._integrations[name] = integration
    
    def unregister(self, name: str) -> bool:
        """
        注销集成
        
        Args:
            name: 集成名称
            
        Returns:
            是否成功注销
        """
        if name in self._integrations:
            del self._integrations[name]
            return True
        return False
    
    def get(self, name: str) -> BaseIntegration | None:
        """
        获取集成
        
        Args:
            name: 集成名称
            
        Returns:
            集成实例或 None
        """
        return self._integrations.get(name)
    
    def list(self) -> list[tuple[str, BaseIntegration]]:
        """
        列出所有集成
        
        Returns:
            (名称, 集成实例) 列表
        """
        return list(self._integrations.items())
    
    async def start_all(self) -> None:
        """启动所有集成"""
        for name, integration in self._integrations.items():
            try:
                await integration.start()
                print(f"集成 {name} 已启动")
            except Exception as e:
                print(f"启动集成 {name} 失败: {e}")

    async def stop_all(self) -> None:
        """停止所有集成"""
        for name, integration in self._integrations.items():
            try:
                await integration.stop()
                print(f"集成 {name} 已停止")
            except Exception as e:
                print(f"停止集成 {name} 失败: {e}")


# 全局注册表实例
_global_registry: IntegrationRegistry | None = None


def get_integration_registry() -> IntegrationRegistry:
    """获取全局集成注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = IntegrationRegistry()
    return _global_registry
