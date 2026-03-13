"""
Skills Registry - 技能注册和管理
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any


class SkillRegistry:
    """Skills 注册表"""
    
    def __init__(self, base_path: str = None):
        self.base_path = Path(base_path) if base_path else Path(__file__).parent.parent.parent.parent / 'skills'
        self.config_path = Path(__file__).parent.parent / 'config'
        self.enabled_skills: Dict[str, dict] = {}
        self._load_registry()
    
    def _load_registry(self):
        """加载注册表"""
        registry_file = self.base_path / 'registry.yaml'
        if registry_file.exists():
            with open(registry_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                self.enabled_skills = data.get('enabled', {}) if data else {}
    
    def _save_registry(self):
        """保存注册表"""
        registry_file = self.base_path / 'registry.yaml'
        with open(registry_file, 'w', encoding='utf-8') as f:
            yaml.dump({'enabled': self.enabled_skills}, f, allow_unicode=True, default_flow_style=False)
    
    def list(self) -> List[dict]:
        """列出所有可用 Skills"""
        skills = []
        for skill_dir in self.base_path.iterdir():
            if skill_dir.is_dir() and not skill_dir.name.startswith('.'):
                skill_md = skill_dir / 'SKILL.md'
                if skill_md.exists():
                    skill_info = self._parse_skill_md(skill_md)
                    skill_info['enabled'] = skill_dir.name in self.enabled_skills
                    skill_info['path'] = str(skill_dir)
                    skills.append(skill_info)
        return skills
    
    def _parse_skill_md(self, path: Path) -> dict:
        """解析 SKILL.md 文件"""
        info = {
            'name': path.parent.name,
            'description': '',
            'location': str(path)
        }
        
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 提取描述
            if '## 描述' in content:
                desc_start = content.find('## 描述') + len('## 描述')
                desc_end = content.find('\n##', desc_start)
                if desc_end == -1:
                    desc_end = len(content)
                info['description'] = content[desc_start:desc_end].strip()
        
        return info
    
    def enable(self, skill_name: str, config: dict = None) -> bool:
        """启用 Skill"""
        skill_path = self.base_path / skill_name
        if not skill_path.exists():
            print(f"Skill '{skill_name}' not found")
            return False
        
        self.enabled_skills[skill_name] = config or {}
        self._save_registry()
        
        # 创建配置文件
        self._create_config(skill_name, config)
        
        print(f"Enabled skill: {skill_name}")
        return True
    
    def disable(self, skill_name: str) -> bool:
        """禁用 Skill"""
        if skill_name in self.enabled_skills:
            del self.enabled_skills[skill_name]
            self._save_registry()
            print(f"Disabled skill: {skill_name}")
            return True
        return False
    
    def is_enabled(self, skill_name: str) -> bool:
        """检查 Skill 是否启用"""
        return skill_name in self.enabled_skills
    
    def get_config(self, skill_name: str) -> Optional[dict]:
        """获取 Skill 配置"""
        config_file = self.config_path / f'{skill_name}.yaml'
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        return self.enabled_skills.get(skill_name, {})
    
    def _create_config(self, skill_name: str, config: dict = None):
        """创建 Skill 配置文件"""
        config_file = self.config_path / f'{skill_name}.yaml'
        if not config_file.exists():
            config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(config_file, 'w', encoding='utf-8') as f:
                yaml.dump(config or {}, f, allow_unicode=True, default_flow_style=False)
    
    def load_skill(self, skill_name: str):
        """加载 Skill 模块"""
        if not self.is_enabled(skill_name):
            raise ValueError(f"Skill '{skill_name}' is not enabled")
        
        skill_path = self.base_path / skill_name
        # 这里可以动态导入 Skill 模块
        return skill_path


# 单例
_registry = None

def get_registry() -> SkillRegistry:
    """获取 Skills 注册表单例"""
    global _registry
    if _registry is None:
        _registry = SkillRegistry()
    return _registry
