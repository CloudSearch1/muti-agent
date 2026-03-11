"""
PI-Python 技能注册表

管理所有已注册的技能
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from .loader import Skill, SkillLoader


class SkillRegistry:
    """技能注册表"""

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        """注册技能"""
        self._skills[skill.name] = skill

    def unregister(self, name: str) -> bool:
        """注销技能"""
        if name in self._skills:
            del self._skills[name]
            return True
        return False

    def get(self, name: str) -> Optional[Skill]:
        """获取技能"""
        return self._skills.get(name)

    def list(self) -> list[Skill]:
        """列出所有技能"""
        return list(self._skills.values())

    def find_matching(self, text: str) -> list[Skill]:
        """
        查找匹配的技能

        Args:
            text: 输入文本

        Returns:
            匹配的技能列表
        """
        matches = []
        for skill in self._skills.values():
            if skill.matches(text):
                matches.append(skill)
        return matches

    def to_system_prompt(self) -> str:
        """
        生成技能系统提示

        Returns:
            包含所有技能描述的系统提示
        """
        if not self._skills:
            return ""

        lines = ["# 可用技能", ""]
        lines.append("你可以使用以下技能来完成任务：")
        lines.append("")

        for skill in self._skills.values():
            lines.append(f"## {skill.name}")
            lines.append(skill.description)

            if skill.triggers:
                lines.append("")
                lines.append("触发词: " + ", ".join(skill.triggers))

            if skill.steps:
                lines.append("")
                lines.append("步骤:")
                for i, step in enumerate(skill.steps, 1):
                    lines.append(f"{i}. {step}")

            lines.append("")

        return "\n".join(lines)

    def load_from_directory(self, skills_dir: Path) -> int:
        """
        从目录加载技能

        Args:
            skills_dir: 技能目录

        Returns:
            加载的技能数量
        """
        count = 0

        for skill_file in SkillLoader.discover(skills_dir):
            try:
                skill = SkillLoader.load(skill_file)
                self.register(skill)
                count += 1
            except Exception:
                continue

        return count

    def clear(self) -> None:
        """清除所有技能"""
        self._skills.clear()


# 全局技能注册表
_global_registry: Optional[SkillRegistry] = None


def get_skill_registry() -> SkillRegistry:
    """获取全局技能注册表"""
    global _global_registry
    if _global_registry is None:
        _global_registry = SkillRegistry()
        # 加载内置技能
        from .loader import create_builtin_skills
        for skill in create_builtin_skills():
            _global_registry.register(skill)
    return _global_registry


def register_skill(skill: Skill) -> None:
    """注册技能到全局注册表"""
    get_skill_registry().register(skill)


def find_skills(text: str) -> list[Skill]:
    """查找匹配的技能"""
    return get_skill_registry().find_matching(text)