"""
功能开关（Feature Flags）

动态控制功能启用/禁用，支持 A/B 测试
"""

import json
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class FlagType(str, Enum):
    """开关类型"""
    BOOLEAN = "boolean"
    PERCENTAGE = "percentage"
    USER_LIST = "user_list"
    A_B_TEST = "ab_test"


@dataclass
class FeatureFlag:
    """功能开关"""
    name: str
    enabled: bool = False
    flag_type: FlagType = FlagType.BOOLEAN
    percentage: float = 0.0  # 百分比（0-100）
    user_list: List[str] = field(default_factory=list)
    variants: Dict[str, Any] = field(default_factory=dict)  # A/B 测试变体
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "flag_type": self.flag_type.value,
            "percentage": self.percentage,
            "user_list": self.user_list,
            "variants": self.variants,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "FeatureFlag":
        return cls(
            name=data["name"],
            enabled=data["enabled"],
            flag_type=FlagType(data["flag_type"]),
            percentage=data.get("percentage", 0.0),
            user_list=data.get("user_list", []),
            variants=data.get("variants", {}),
            metadata=data.get("metadata", {}),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow(),
            updated_at=datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.utcnow(),
        )


class FeatureFlagManager:
    """
    功能开关管理器
    
    功能:
    - 动态启用/禁用
    - 百分比灰度
    - 用户白名单
    - A/B 测试
    - 审计日志
    """
    
    def __init__(self, storage_path: str = "data/feature_flags.json"):
        self.storage_path = storage_path
        self.flags: Dict[str, FeatureFlag] = {}
        self._audit_log: List[Dict[str, Any]] = []
        
        self._load_flags()
        logger.info(f"FeatureFlagManager initialized: {len(self.flags)} flags loaded")
    
    def _load_flags(self):
        """加载开关"""
        try:
            import os
            from pathlib import Path
            
            path = Path(self.storage_path)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.flags = {
                        name: FeatureFlag.from_dict(flag_data)
                        for name, flag_data in data.items()
                    }
        except Exception as e:
            logger.error(f"Load flags failed: {e}")
    
    def _save_flags(self):
        """保存开关"""
        try:
            from pathlib import Path
            
            path = Path(self.storage_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, "w", encoding="utf-8") as f:
                json.dump(
                    {name: flag.to_dict() for name, flag in self.flags.items()},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"Save flags failed: {e}")
    
    def create_flag(
        self,
        name: str,
        enabled: bool = False,
        flag_type: FlagType = FlagType.BOOLEAN,
        **kwargs,
    ) -> FeatureFlag:
        """创建开关"""
        if name in self.flags:
            raise ValueError(f"Flag already exists: {name}")
        
        flag = FeatureFlag(
            name=name,
            enabled=enabled,
            flag_type=flag_type,
            **kwargs,
        )
        
        self.flags[name] = flag
        self._save_flags()
        
        logger.info(f"Flag created: {name}")
        self._audit("create", name, {"enabled": enabled})
        
        return flag
    
    def update_flag(self, name: str, **updates) -> FeatureFlag:
        """更新开关"""
        if name not in self.flags:
            raise ValueError(f"Flag not found: {name}")
        
        flag = self.flags[name]
        
        for key, value in updates.items():
            if hasattr(flag, key):
                setattr(flag, key, value)
        
        flag.updated_at = datetime.utcnow()
        self._save_flags()
        
        logger.info(f"Flag updated: {name}")
        self._audit("update", name, updates)
        
        return flag
    
    def delete_flag(self, name: str):
        """删除开关"""
        if name in self.flags:
            del self.flags[name]
            self._save_flags()
            
            logger.info(f"Flag deleted: {name}")
            self._audit("delete", name)
    
    def is_enabled(self, name: str, user_id: Optional[str] = None) -> bool:
        """
        检查开关是否启用
        
        Args:
            name: 开关名称
            user_id: 用户 ID（用于百分比和用户列表）
        
        Returns:
            是否启用
        """
        if name not in self.flags:
            return False
        
        flag = self.flags[name]
        
        if not flag.enabled:
            return False
        
        # 根据类型判断
        if flag.flag_type == FlagType.BOOLEAN:
            return flag.enabled
        
        elif flag.flag_type == FlagType.PERCENTAGE:
            if user_id is None:
                return False
            
            # 基于用户 ID 哈希计算百分比
            import hashlib
            hash_value = int(hashlib.md5(f"{name}:{user_id}".encode()).hexdigest(), 16)
            percentage = hash_value % 100
            
            return percentage < flag.percentage
        
        elif flag.flag_type == FlagType.USER_LIST:
            return user_id in flag.user_list
        
        elif flag.flag_type == FlagType.A_B_TEST:
            # A/B 测试逻辑
            if user_id is None:
                return False
            
            import hashlib
            hash_value = int(hashlib.md5(f"{name}:{user_id}".encode()).hexdigest(), 16)
            variant_index = hash_value % len(flag.variants)
            
            return list(flag.variants.keys())[variant_index]
        
        return False
    
    def get_variant(self, name: str, user_id: Optional[str] = None) -> Any:
        """获取 A/B 测试变体"""
        if name not in self.flags:
            return None
        
        flag = self.flags[name]
        
        if flag.flag_type != FlagType.A_B_TEST:
            return None
        
        if user_id is None:
            return list(flag.variants.values())[0]
        
        import hashlib
        hash_value = int(hashlib.md5(f"{name}:{user_id}".encode()).hexdigest(), 16)
        variant_index = hash_value % len(flag.variants)
        
        return list(flag.variants.values())[variant_index]
    
    def list_flags(self) -> List[Dict[str, Any]]:
        """列出所有开关"""
        return [flag.to_dict() for flag in self.flags.values()]
    
    def get_audit_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """获取审计日志"""
        return self._audit_log[-limit:]
    
    def _audit(self, action: str, flag_name: str, changes: Optional[Dict] = None):
        """记录审计"""
        self._audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": action,
            "flag_name": flag_name,
            "changes": changes or {},
        })
        
        # 限制日志大小
        if len(self._audit_log) > 1000:
            self._audit_log = self._audit_log[-1000:]


# ============ 装饰器 ============

def feature_flag(flag_name: str, fallback: Any = None):
    """
    功能开关装饰器
    
    用法:
        @feature_flag("new_feature")
        async def new_feature_function():
            ...
    """
    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            manager = get_feature_flag_manager()
            
            if manager.is_enabled(flag_name):
                return await func(*args, **kwargs)
            else:
                logger.info(f"Feature flag disabled: {flag_name}")
                return fallback
        
        return wrapper
    return decorator


# ============ 全局管理器 ============

_manager: Optional[FeatureFlagManager] = None


def get_feature_flag_manager() -> FeatureFlagManager:
    """获取管理器"""
    global _manager
    if _manager is None:
        _manager = FeatureFlagManager()
    return _manager


def init_feature_flags(**kwargs) -> FeatureFlagManager:
    """初始化功能开关"""
    global _manager
    _manager = FeatureFlagManager(**kwargs)
    logger.info("Feature flags initialized")
    return _manager
