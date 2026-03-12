"""
PI-Python 技能加载器

解析 Markdown 技能文件
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "Skill",
    "SkillLoader",
    "create_builtin_skills",
]


@dataclass
class Skill:
    """
    技能定义

    遵循 Agent Skills 标准 (https://agentskills.io)
    """
    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    path: Path | None = None
    raw_content: str = ""

    def matches(self, text: str) -> bool:
        """检查文本是否匹配技能触发条件"""
        text_lower = text.lower()
        for trigger in self.triggers:
            if trigger.lower() in text_lower:
                return True
        return False

    def to_prompt(self) -> str:
        """生成技能提示"""
        lines = [f"## {self.name}", "", self.description]

        if self.steps:
            lines.append("")
            lines.append("### 步骤")
            for i, step in enumerate(self.steps, 1):
                lines.append(f"{i}. {step}")

        if self.examples:
            lines.append("")
            lines.append("### 示例")
            for example in self.examples:
                lines.append(f"- {example}")

        return "\n".join(lines)


class SkillLoader:
    """技能加载器"""

    @classmethod
    def load(cls, path: Path) -> Skill:
        """
        从 Markdown 文件加载技能

        Args:
            path: 技能文件路径

        Returns:
            Skill: 技能对象
        """
        content = path.read_text(encoding="utf-8")

        name = cls._extract_title(content)
        description = (
            cls._extract_section(content, "描述") or
            cls._extract_section(content, "Description") or
            ""
        )
        triggers = (
            cls._extract_list(content, "触发") or
            cls._extract_list(content, "Triggers") or
            []
        )
        steps = (
            cls._extract_list(content, "步骤") or
            cls._extract_list(content, "Steps") or
            []
        )
        examples = (
            cls._extract_list(content, "示例") or
            cls._extract_list(content, "Examples") or
            []
        )

        return Skill(
            name=name,
            description=description,
            triggers=triggers,
            steps=steps,
            examples=examples,
            path=path,
            raw_content=content
        )

    @staticmethod
    def _extract_title(content: str) -> str:
        """提取标题"""
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        return match.group(1).strip() if match else "Unknown"

    @staticmethod
    def _extract_section(content: str, heading: str) -> str | None:
        """提取章节内容"""
        # 支持中英文
        patterns = [
            rf"^##\s+{re.escape(heading)}\s*\n(.+?)(?=\n##|\Z)",
            rf"^##\s+{re.escape(heading)}\s*?\n(.+?)(?=\n##|\Z)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
            if match:
                return match.group(1).strip()

        return None

    @staticmethod
    def _extract_list(content: str, heading: str) -> list[str]:
        """提取列表项"""
        section = SkillLoader._extract_section(content, heading)
        if not section:
            return []

        items = []
        for line in section.split("\n"):
            line = line.strip()

            # 数字列表
            match = re.match(r"^\d+\.\s+(.+)$", line)
            if match:
                items.append(match.group(1).strip())
                continue

            # 无序列表
            match = re.match(r"^[-*]\s+(.+)$", line)
            if match:
                items.append(match.group(1).strip())
                continue

            # 简单文本
            if line and not line.startswith("#"):
                items.append(line)

        return items

    @classmethod
    def discover(cls, skills_dir: Path) -> list[Path]:
        """
        发现技能文件

        Args:
            skills_dir: 技能目录

        Returns:
            技能文件路径列表
        """
        if not skills_dir.exists():
            return []

        # 查找 SKILL.md 或 *.skill.md 文件
        skill_files = []

        # 1. 查找 SKILL.md 文件（子目录形式）
        for subdir in skills_dir.iterdir():
            if subdir.is_dir():
                skill_file = subdir / "SKILL.md"
                if skill_file.exists():
                    skill_files.append(skill_file)

        # 2. 查找 *.skill.md 文件
        for skill_file in skills_dir.glob("*.skill.md"):
            skill_files.append(skill_file)

        # 3. 查找 *.md 文件（根目录）
        for skill_file in skills_dir.glob("*.md"):
            if skill_file not in skill_files:
                skill_files.append(skill_file)

        return skill_files


def _create_code_review_skill() -> Skill:
    """创建代码审查技能"""
    return Skill(
        name="Code Review",
        description="审查代码变更并提供反馈",
        triggers=["代码审查", "review", "审查代码"],
        steps=[
            "阅读提供的代码变更",
            "分析代码质量和潜在问题",
            "检查是否有安全漏洞",
            "提供改进建议",
            "生成审查报告"
        ],
        examples=[
            "请审查这段代码",
            "Review PR #123"
        ]
    )


def _create_debug_skill() -> Skill:
    """创建调试技能"""
    return Skill(
        name="Debug",
        description="帮助调试代码问题",
        triggers=["调试", "debug", "报错", "错误"],
        steps=[
            "分析错误信息",
            "定位问题代码",
            "解释错误原因",
            "提供修复建议",
            "验证修复方案"
        ],
        examples=[
            "帮我调试这个问题",
            "Debug this error"
        ]
    )


def _create_docs_skill() -> Skill:
    """创建文档生成技能"""
    return Skill(
        name="Generate Documentation",
        description="为代码生成文档",
        triggers=["生成文档", "文档", "documentation", "docstring"],
        steps=[
            "分析代码结构",
            "提取函数和类的信息",
            "生成文档字符串",
            "创建 API 文档",
            "添加使用示例"
        ],
        examples=[
            "为这个函数生成文档",
            "Generate docs for this module"
        ]
    )


def create_builtin_skills() -> list[Skill]:
    """创建内置技能"""
    return [
        _create_code_review_skill(),
        _create_debug_skill(),
        _create_docs_skill(),
    ]
