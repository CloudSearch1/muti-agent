"""
Skills Loader - 技能加载器
"""

import os
import sys
import importlib.util
from pathlib import Path
from typing import Optional, Any


class SkillLoader:
    """Skills 加载器"""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path) if base_path else Path(__file__).parent.parent.parent.parent / 'skills'
        self.loaded_skills = {}
    
    def load(self, skill_name: str) -> Optional[Any]:
        """加载 Skill"""
        if skill_name in self.loaded_skills:
            return self.loaded_skills[skill_name]
        
        skill_path = self.base_path / skill_name
        if not skill_path.exists():
            return None
        
        # 尝试加载 skill.py 如果存在
        skill_module = skill_path / 'skill.py'
        if skill_module.exists():
            module = self._load_module(skill_name, skill_module)
            self.loaded_skills[skill_name] = module
            return module
        
        # 否则返回路径信息
        return {'path': str(skill_path), 'name': skill_name}
    
    def _load_module(self, name: str, path: Path):
        """动态加载模块"""
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    
    def unload(self, skill_name: str):
        """卸载 Skill"""
        if skill_name in self.loaded_skills:
            del self.loaded_skills[skill_name]
    
    def reload(self, skill_name: str) -> Optional[Any]:
        """重新加载 Skill"""
        self.unload(skill_name)
        return self.load(skill_name)
    
    def list_loaded(self) -> list:
        """列出已加载的 Skills"""
        return list(self.loaded_skills.keys())


def load_skill(skill_name: str, base_path: str = None) -> Optional[Any]:
    """便捷函数：加载 Skill"""
    loader = SkillLoader(base_path)
    return loader.load(skill_name)
