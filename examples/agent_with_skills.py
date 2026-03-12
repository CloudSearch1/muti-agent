"""
Agent + Skills 集成使用示例

参考 OpenClaw 的 Skills 使用方式
"""

import asyncio
from pathlib import Path

from pi_python.agent import Agent, AgentState
from pi_python.ai import get_model
from pi_python.skills import SkillLoader, SkillRegistry, create_builtin_skills


async def main():
    """主函数"""
    print("=" * 60)
    print("Agent + Skills 集成示例")
    print("=" * 60)
    print()

    # 1. 创建 Agent
    print("【步骤 1】创建 Agent")
    print("-" * 40)

    model = get_model("openai", "gpt-4o")

    agent = Agent(
        AgentState(
            system_prompt="你是一个智能助手，可以帮助用户完成各种任务。",
            model=model,
        )
    )
    print("✅ Agent 创建成功")
    print()

    # 2. 设置 Skills 注册表
    print("【步骤 2】设置 Skills 注册表")
    print("-" * 40)

    registry = SkillRegistry()
    agent.set_skill_registry(registry)
    print("✅ Skills 注册表已设置")
    print()

    # 3. 加载内置 Skills
    print("【步骤 3】加载内置 Skills")
    print("-" * 40)

    builtin_skills = create_builtin_skills()
    for skill in builtin_skills:
        agent.register_skill(skill)
        print(f"  📋 已加载: {skill.name}")
    print()

    # 4. 显示可用的 Skills
    print("【步骤 4】显示可用的 Skills")
    print("-" * 40)

    skills_prompt = agent.format_skills_for_prompt()
    print(skills_prompt)
    print()

    # 5. 测试 Skills 匹配
    print("【步骤 5】测试 Skills 匹配")
    print("-" * 40)

    test_queries = [
        "帮我审查这段代码",
        "这个 bug 怎么修",
        "生成文档",
        "普通的问题",
    ]

    for query in test_queries:
        matched = agent.match_skills(query)
        if matched:
            skill_names = [s.name for s in matched]
            print(f"  '{query}' -> ✅ 匹配: {', '.join(skill_names)}")
        else:
            print(f"  '{query}' -> ❌ 无匹配")
    print()

    # 6. 演示 Skills 注入
    print("【步骤 6】演示 Skills 注入")
    print("-" * 40)

    # 匹配技能
    user_input = "帮我审查这段代码"
    matched_skills = agent.match_skills(user_input)

    if matched_skills:
        print(f"用户输入: '{user_input}'")
        print(f"匹配技能: {matched_skills[0].name}")
        print()

        # 注入技能指令
        instructions = agent.inject_skill_instructions(matched_skills)
        print("注入的技能指令:")
        print("-" * 40)
        print(instructions[:500] + "..." if len(instructions) > 500 else instructions)
        print()

    # 7. 完整的工作流程演示
    print("【步骤 7】完整工作流程演示")
    print("-" * 40)
    print("在实际应用中，Agent 会自动:")
    print("  1. 接收用户输入")
    print("  2. 匹配 Skills")
    print("  3. 注入技能指令到系统提示词")
    print("  4. 调用 LLM 生成响应")
    print("  5. 返回结果给用户")
    print()

    # 8. 使用 prompt_with_skills 方法
    print("【步骤 8】使用 prompt_with_skills 方法")
    print("-" * 40)
    print("调用: agent.prompt_with_skills('帮我审查代码')")
    print("  -> 自动匹配 Code Review 技能")
    print("  -> 自动注入技能指令")
    print("  -> 生成响应")
    print()

    # 注意：实际调用需要 API key，这里仅演示流程
    print("⚠️  注意：实际调用需要配置 API key")
    print()

    print("=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
