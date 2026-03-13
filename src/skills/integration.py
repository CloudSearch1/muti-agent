"""
Skills Integration - 技能集成到 Agent 系统

将 10 个 Claude Code Skills 集成到现有的 Agent 系统中
"""

from typing import Optional, Dict, Any
from pathlib import Path

from .registry import get_registry
from .config import SkillConfig


class SkillsIntegration:
    """Skills 集成管理器"""
    
    def __init__(self):
        self.registry = get_registry()
        self.config = SkillConfig()
        self._hooks: Dict[str, list] = {}
        self._setup_hooks()
    
    def _setup_hooks(self):
        """设置集成钩子"""
        self._hooks = {
            'on_task_start': [],
            'on_task_complete': [],
            'on_code_generate': [],
            'on_code_review': [],
            'on_ui_generate': [],
            'on_test_generate': [],
        }
    
    def register_hook(self, event: str, callback):
        """注册事件钩子"""
        if event in self._hooks:
            self._hooks[event].append(callback)
    
    def trigger(self, event: str, data: Any = None):
        """触发事件"""
        if event in self._hooks:
            for callback in self._hooks[event]:
                try:
                    callback(data)
                except Exception as e:
                    print(f"Hook error on {event}: {e}")
    
    # ========== Skill 集成方法 ==========
    
    def apply_superpowers(self, task: dict) -> dict:
        """应用 Superpowers Skill"""
        if not self.registry.is_enabled('superpowers'):
            return task
        
        config = self.config.load('superpowers')
        if config and config.get('superpowers', {}).get('brainstorming', {}).get('enabled'):
            # 启动 brainstorming
            task['brainstorming'] = True
        if config and config.get('superpowers', {}).get('tdd', {}).get('enabled'):
            # 启动 TDD
            task['tdd'] = True
        
        return task
    
    def apply_planning(self, task: dict) -> dict:
        """应用 Planning with Files Skill"""
        if not self.registry.is_enabled('planning-with-files'):
            return task
        
        config = self.config.load('planning')
        if config and config.get('planning', {}).get('persistence', {}).get('enabled'):
            # 创建任务规划文件
            task['persist'] = True
            task['checkpoint_interval'] = config['planning']['persistence'].get('auto_save_interval', 300)
        
        return task
    
    def apply_ui_ux(self, spec: dict) -> dict:
        """应用 UI UX Pro Max Skill"""
        if not self.registry.is_enabled('ui-ux-pro-max'):
            return spec
        
        config = self.config.load('ui-ux')
        if config:
            ui_config = config.get('ui_ux', {})
            spec['style'] = spec.get('style', ui_config.get('styles', {}).get('default', 'modern-minimalist'))
            spec['colors'] = spec.get('colors', ui_config.get('colors', {}).get('default_scheme', 'professional-blue'))
            spec['responsive'] = ui_config.get('generation', {}).get('responsive', True)
        
        return spec
    
    def apply_code_review(self, code: str, context: dict) -> dict:
        """应用 Code Review Skill"""
        if not self.registry.is_enabled('code-review'):
            return {'reviewed': False, 'code': code}
        
        config = self.config.load('code-review')
        review_config = config.get('code_review', {}) if config else {}
        
        return {
            'reviewed': True,
            'code': code,
            'parallel': review_config.get('parallel', {}).get('enabled', True),
            'confidence_threshold': review_config.get('confidence', {}).get('threshold', 0.7),
        }
    
    def apply_simplifier(self, code: str) -> str:
        """应用 Code Simplifier Skill"""
        if not self.registry.is_enabled('code-simplifier'):
            return code
        
        config = self.config.load('simplifier')
        if config and config.get('simplifier', {}).get('enabled'):
            # 标记需要简化
            return code  # 实际简化由 code_simplifier 工具执行
        
        return code
    
    def apply_webapp_testing(self, ui_spec: dict) -> dict:
        """应用 Webapp Testing Skill"""
        if not self.registry.is_enabled('webapp-testing'):
            return {'tests_generated': False}
        
        config = self.config.load('webapp-testing')
        if config and config.get('webapp_testing', {}).get('test_generation', {}).get('auto_generate'):
            return {
                'tests_generated': True,
                'include_visual': config['webapp_testing']['test_generation'].get('include_visual', True),
            }
        
        return {'tests_generated': False}
    
    def apply_ralph_loop(self, task: dict) -> dict:
        """应用 Ralph Loop Skill"""
        if not self.registry.is_enabled('ralph-loop'):
            return task
        
        config = self.config.load('ralph')
        if config:
            ralph_config = config.get('ralph_loop', {})
            task['ralph_validation'] = True
            task['max_loops'] = ralph_config.get('validation', {}).get('max_attempts', 5)
            task['checks'] = ralph_config.get('checks', [])
        
        return task
    
    def apply_mcp(self, tool: dict) -> dict:
        """应用 MCP Builder Skill"""
        if not self.registry.is_enabled('mcp-builder'):
            return tool
        
        config = self.config.load('mcp')
        if config and config.get('mcp', {}).get('tools', {}).get('auto_generate'):
            tool['mcp_wrapped'] = True
            tool['mcp_auto_boundaries'] = True
        
        return tool
    
    def apply_pptx(self, data: dict) -> dict:
        """应用 PPTX Skill"""
        if not self.registry.is_enabled('pptx'):
            return {'generated': False}
        
        config = self.config.load('pptx')
        if config:
            pptx_config = config.get('pptx', {})
            return {
                'generated': True,
                'template': pptx_config.get('templates', {}).get('default', 'project-report'),
                'formats': pptx_config.get('output', {}).get('formats', ['pptx', 'pdf']),
            }
        
        return {'generated': False}
    
    def apply_skill_creator(self, skill_spec: dict) -> dict:
        """应用 Skill Creator Skill"""
        if not self.registry.is_enabled('skill-creator'):
            return {'created': False}
        
        config = self.config.load('skill-creator')
        if config:
            creator_config = config.get('skill_creator', {})
            return {
                'created': True,
                'template': creator_config.get('templates', {}).get('default', 'basic'),
                'output_dir': creator_config.get('output', {}).get('base_dir', 'skills/custom/'),
                'auto_test': creator_config.get('testing', {}).get('run_on_create', True),
            }
        
        return {'created': False}


# 单例
_integration = None

def get_integration() -> SkillsIntegration:
    """获取 Skills 集成单例"""
    global _integration
    if _integration is None:
        _integration = SkillsIntegration()
    return _integration
