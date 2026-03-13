"""
Skills Config - 技能配置管理
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class SkillConfig:
    """Skills 配置管理器"""
    
    def __init__(self, config_dir: str = None):
        self.config_dir = Path(config_dir) if config_dir else Path(__file__).parent / 'config'
        self._configs: Dict[str, dict] = {}
    
    def load(self, skill_name: str) -> Optional[dict]:
        """加载 Skill 配置"""
        if skill_name in self._configs:
            return self._configs[skill_name]
        
        config_file = self.config_dir / f'{skill_name}.yaml'
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self._configs[skill_name] = config
                return config
        return None
    
    def save(self, skill_name: str, config: dict):
        """保存 Skill 配置"""
        config_file = self.config_dir / f'{skill_name}.yaml'
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        self._configs[skill_name] = config
    
    def get(self, skill_name: str, key: str, default: Any = None) -> Any:
        """获取配置项"""
        config = self.load(skill_name)
        if config:
            return config.get(key, default)
        return default
    
    def set(self, skill_name: str, key: str, value: Any):
        """设置配置项"""
        config = self.load(skill_name) or {}
        config[key] = value
        self.save(skill_name, config)
    
    def all(self) -> Dict[str, dict]:
        """获取所有配置"""
        configs = {}
        for config_file in self.config_dir.glob('*.yaml'):
            skill_name = config_file.stem
            configs[skill_name] = self.load(skill_name)
        return configs


def get_config(skill_name: str, config_dir: str = None) -> Optional[dict]:
    """便捷函数：获取 Skill 配置"""
    config = SkillConfig(config_dir)
    return config.load(skill_name)
