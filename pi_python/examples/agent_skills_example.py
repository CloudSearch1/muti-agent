"""
Agent 与 Skills 集成示例

演示如何使用 Agent 与 Skills 进行交互：
1. 基本的 Skills 自动匹配
2. 手动注册自定义 Skills
3. 动态加载 Skill 指令
4. 多 Skills 组合使用
"""

from __future__ import annotations

import asyncio
from pathlib import Path

# 导入 pi_python 模块
from pi_python import (
    Agent,
    AgentState,
    AgentEvent,
    AgentEventType,
    Model,
    Skill,
    SkillRegistry,
    get_skill_registry,
    register_skill,
)


def create_custom_skill() -> Skill:
    """创建自定义技能"""
    return Skill(
        name="CodeGenerator",
        description="根据自然语言描述生成代码",
        triggers=["生成代码", "generate code", "写代码", "code"],
        steps=[
            "理解用户需求",
            "设计代码结构",
            "编写代码实现",
            "添加必要注释",
            "验证代码正确性"
        ],
        examples=[
            "生成一个 Python 函数计算斐波那契数列",
            "写一个 JavaScript 函数验证邮箱格式"
        ]
    )


def create_another_skill() -> Skill:
    """创建另一个自定义技能"""
    return Skill(
        name="Translator",
        description="将文本翻译成不同语言",
        triggers=["翻译", "translate", "translation"],
        steps=[
            "识别源语言",
            "确定目标语言",
            "进行翻译",
            "检查翻译质量"
        ],
        examples=[
            "将这段英文翻译成中文",
            "Translate this to French"
        ]
    )


def print_separator(title: str = "") -> None:
    """打印分隔线"""
    print("\n" + "=" * 60)
    if title:
        print(f" {title}")
        print("=" * 60)


def example_1_basic_skills() -> None:
    """示例 1: 基本的 Skills 使用"""
    print_separator("示例 1: 基本 Skills 使用")

    # 获取全局技能注册表
    registry = get_skill_registry()

    # 列出所有已注册的技能
    print("\n已注册的技能:")
    for skill in registry.list():
        print(f"  - {skill.name}: {skill.description}")
        if skill.triggers:
            print(f"    触发词: {', '.join(skill.triggers)}")

    # 匹配技能
    test_inputs = [
        "请帮我 review 这段代码",
        "我需要调试一个 bug",
        "帮我生成文档",
    ]

    print("\n技能匹配测试:")
    for text in test_inputs:
        matched = registry.find_matching(text)
        if matched:
            print(f"  '{text}' -> 匹配: {[s.name for s in matched]}")
        else:
            print(f"  '{text}' -> 无匹配")


def example_2_custom_skills() -> None:
    """示例 2: 注册自定义技能"""
    print_separator("示例 2: 注册自定义技能")

    # 创建新的技能注册表
    registry = SkillRegistry()

    # 注册自定义技能
    skill1 = create_custom_skill()
    skill2 = create_another_skill()

    registry.register(skill1)
    registry.register(skill2)

    print(f"\n已注册 {registry.list().__len__()} 个自定义技能:")
    for skill in registry.list():
        print(f"  - {skill.name}")

    # 测试匹配
    test_inputs = [
        "帮我生成一个 Python 函数",
        "请翻译这段文字",
        "我需要写一些代码",
    ]

    print("\n匹配测试:")
    for text in test_inputs:
        matched = registry.find_matching(text)
        if matched:
            print(f"  '{text}' -> 匹配: {[s.name for s in matched]}")


def example_3_skill_prompt_format() -> None:
    """示例 3: 技能提示词格式化"""
    print_separator("示例 3: 技能提示词格式化")

    registry = SkillRegistry()
    registry.register(create_custom_skill())
    registry.register(create_another_skill())

    # 生成系统提示词
    prompt = registry.to_system_prompt()
    print("\n生成的系统提示词:")
    print(prompt)


def example_4_agent_skills_integration() -> None:
    """示例 4: Agent 与 Skills 集成"""
    print_separator("示例 4: Agent 与 Skills 集成")

    # 创建技能注册表
    registry = SkillRegistry()
    registry.register(create_custom_skill())
    registry.register(create_another_skill())

    # 创建 AgentState（使用模拟模型）
    # 注意：这里需要实际的模型配置才能运行
    print("\nAgent 配置:")
    print(f"  - 技能注册表: {registry.list().__len__()} 个技能")
    print(f"  - 自动匹配技能: 启用")

    # 格式化技能提示词
    print("\n技能提示词格式:")
    lines = [
        "",
        "# Available Skills",
        "",
        "Skills provide specialized capabilities. Invoke with: skill: \"<name>\"",
        "",
    ]
    for skill in registry.list():
        trigger_hint = f" - trigger: {', '.join(skill.triggers[:3])}" if skill.triggers else ""
        lines.append(f"- **{skill.name}**: {skill.description}{trigger_hint}")

    lines.append("")
    lines.append("When a skill matches the user's request, follow its guidance.")

    print("\n".join(lines))


def example_5_dynamic_skill_injection() -> None:
    """示例 5: 动态技能注入"""
    print_separator("示例 5: 动态技能注入")

    registry = SkillRegistry()
    registry.register(create_custom_skill())

    # 匹配用户输入
    user_input = "帮我生成一个 Python 函数计算阶乘"
    matched = registry.find_matching(user_input)

    print(f"\n用户输入: '{user_input}'")
    print(f"匹配的技能: {[s.name for s in matched]}")

    # 注入详细指令
    if matched:
        print("\n注入的技能指令:")
        for skill in matched:
            print(f"\n{skill.to_prompt()}")


def example_6_multiple_skills() -> None:
    """示例 6: 多技能组合"""
    print_separator("示例 6: 多技能组合")

    registry = SkillRegistry()

    # 注册多个技能
    skills = [
        Skill(
            name="CodeReview",
            description="审查代码质量",
            triggers=["review", "审查"],
            steps=["检查代码风格", "分析潜在问题", "提出改进建议"]
        ),
        Skill(
            name="TestGenerator",
            description="生成测试代码",
            triggers=["test", "测试"],
            steps=["分析代码逻辑", "设计测试用例", "生成测试代码"]
        ),
        Skill(
            name="DocGenerator",
            description="生成文档",
            triggers=["doc", "文档"],
            steps=["分析代码结构", "提取接口信息", "生成文档"]
        ),
    ]

    for skill in skills:
        registry.register(skill)

    # 测试多技能匹配
    test_input = "请 review 这段代码并生成测试"
    matched = registry.find_matching(test_input)

    print(f"\n输入: '{test_input}'")
    print(f"匹配的技能: {[s.name for s in matched]}")

    # 组合注入
    if matched:
        print("\n组合注入的指令:")
        combined = ["# Active Skills\n"]
        for skill in matched:
            combined.append(f"## {skill.name}")
            combined.append(skill.description)
            combined.append(f"步骤: {', '.join(skill.steps)}")
            combined.append("")

        print("\n".join(combined))


def main() -> None:
    """运行所有示例"""
    print("\n" + "=" * 60)
    print(" Agent 与 Skills 集成示例")
    print("=" * 60)

    example_1_basic_skills()
    example_2_custom_skills()
    example_3_skill_prompt_format()
    example_4_agent_skills_integration()
    example_5_dynamic_skill_injection()
    example_6_multiple_skills()

    print_separator("示例完成")
    print("\n以上示例展示了 Agent 与 Skills 的集成方式：")
    print("  1. Skills 在系统提示词中显示为紧凑列表")
    print("  2. Agent 按需加载 Skill 指令（使用 match_skills 方法）")
    print("  3. Skills 是指导而非控制")
    print("  4. 支持动态加载和注入")
    print("  5. 支持多 Skills 组合")


if __name__ == "__main__":
    main()