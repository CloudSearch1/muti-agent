"""
IntelliTeam Skills Registry

集成 10 个顶级 Claude Code Skills:
1. superpowers - 核心开发 Agent 能力
2. planning-with-files - 任务规划持久化
3. ui-ux-pro-max - 前端生成质量提升
4. code-review - 多 Agent 代码审查
5. code-simplifier - 自动代码优化
6. webapp-testing - 前端自动化测试
7. ralph-loop - 任务完成保障
8. mcp-builder - 工具系统扩展
9. pptx - 文档生成能力
10. skill-creator - 自定义能力
"""

from .registry import SkillRegistry
from .loader import SkillLoader
from .config import SkillConfig

__all__ = [
    'SkillRegistry',
    'SkillLoader', 
    'SkillConfig',
]

# 可用 Skills 列表
AVAILABLE_SKILLS = [
    'superpowers',
    'planning-with-files',
    'ui-ux-pro-max',
    'code-review',
    'code-simplifier',
    'webapp-testing',
    'ralph-loop',
    'mcp-builder',
    'pptx',
    'skill-creator',
]
