"""
PI-Python 技能测试

测试 skills 模块的技能加载和注册表功能
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from pi_python.skills.loader import Skill, SkillLoader, create_builtin_skills
from pi_python.skills.registry import (
    SkillRegistry,
    get_skill_registry,
    register_skill,
    find_skills,
)


class TestSkill:
    """技能数据类测试"""

    def test_skill_creation(self):
        """测试技能创建"""
        skill = Skill(
            name="Test Skill",
            description="A test skill",
            triggers=["test", "testing"],
            steps=["Step 1", "Step 2"],
            examples=["Example 1"]
        )

        assert skill.name == "Test Skill"
        assert skill.description == "A test skill"
        assert skill.triggers == ["test", "testing"]
        assert skill.steps == ["Step 1", "Step 2"]
        assert skill.examples == ["Example 1"]

    def test_skill_defaults(self):
        """测试技能默认值"""
        skill = Skill(name="Minimal Skill", description="Minimal")

        assert skill.triggers == []
        assert skill.steps == []
        assert skill.examples == []
        assert skill.path is None
        assert skill.raw_content == ""

    def test_skill_matches_trigger(self):
        """测试技能触发匹配"""
        skill = Skill(
            name="Test",
            description="Test",
            triggers=["代码审查", "review"]
        )

        assert skill.matches("请进行代码审查") is True
        assert skill.matches("Review this code") is True
        assert skill.matches("review the changes") is True

    def test_skill_matches_no_trigger(self):
        """测试技能无触发"""
        skill = Skill(
            name="Test",
            description="Test",
            triggers=["debug"]
        )

        assert skill.matches("Hello world") is False
        assert skill.matches("Please help") is False

    def test_skill_matches_case_insensitive(self):
        """测试技能匹配大小写不敏感"""
        skill = Skill(
            name="Test",
            description="Test",
            triggers=["DEBUG"]
        )

        assert skill.matches("debug this") is True
        assert skill.matches("Debug this") is True
        assert skill.matches("DEBUG this") is True

    def test_skill_to_prompt(self):
        """测试生成技能提示"""
        skill = Skill(
            name="Code Review",
            description="Review code changes",
            triggers=["review", "审查"],
            steps=["Read code", "Find issues", "Suggest fixes"],
            examples=["Review PR #123", "审查这段代码"]
        )

        prompt = skill.to_prompt()

        assert "## Code Review" in prompt
        assert "Review code changes" in prompt
        assert "### 步骤" in prompt
        assert "1. Read code" in prompt
        assert "2. Find issues" in prompt
        assert "3. Suggest fixes" in prompt
        assert "### 示例" in prompt
        assert "- Review PR #123" in prompt

    def test_skill_to_prompt_minimal(self):
        """测试生成最小技能提示"""
        skill = Skill(name="Simple", description="Simple skill")

        prompt = skill.to_prompt()

        assert "## Simple" in prompt
        assert "Simple skill" in prompt
        assert "### 步骤" not in prompt
        assert "### 示例" not in prompt


class TestSkillLoader:
    """技能加载器测试"""

    def test_extract_title(self):
        """测试提取标题"""
        content = "# My Skill\n\nThis is my skill."
        title = SkillLoader._extract_title(content)
        assert title == "My Skill"

    def test_extract_title_no_title(self):
        """测试无标题"""
        content = "No title here"
        title = SkillLoader._extract_title(content)
        assert title == "Unknown"

    def test_extract_section(self):
        """测试提取章节"""
        content = """# My Skill

## 描述
This is the description.

## 步骤
Step content here.
"""
        section = SkillLoader._extract_section(content, "描述")
        assert "This is the description" in section

    def test_extract_section_english(self):
        """测试提取英文章节"""
        content = """# My Skill

## Description
This is the description.

## Steps
Step content here.
"""
        section = SkillLoader._extract_section(content, "Description")
        assert "This is the description" in section

    def test_extract_section_not_found(self):
        """测试章节不存在"""
        content = "# My Skill\n\n## Other\nContent"
        section = SkillLoader._extract_section(content, "描述")
        assert section is None

    def test_extract_list_numbered(self):
        """测试提取数字列表"""
        content = """## 步骤

1. First step
2. Second step
3. Third step
"""
        items = SkillLoader._extract_list(content, "步骤")

        assert len(items) == 3
        assert "First step" in items
        assert "Second step" in items
        assert "Third step" in items

    def test_extract_list_bulleted(self):
        """测试提取无序列表"""
        content = """## 触发

- trigger one
- trigger two
* trigger three
"""
        items = SkillLoader._extract_list(content, "触发")

        assert len(items) == 3
        assert "trigger one" in items
        assert "trigger two" in items
        assert "trigger three" in items

    def test_extract_list_mixed(self):
        """测试提取混合列表"""
        content = """## 步骤

1. Numbered item
- Bullet item
* Another bullet
Plain text item
"""
        items = SkillLoader._extract_list(content, "步骤")

        assert len(items) >= 3  # 至少包含列表项

    def test_load_skill(self, tmp_path: Path):
        """测试加载技能文件"""
        skill_file = tmp_path / "test_skill.md"
        skill_file.write_text("""# Code Review

## 描述
Review code and provide feedback.

## 触发
- 代码审查
- review

## 步骤
1. Read the code
2. Find issues
3. Suggest improvements

## 示例
- Review this code
- 审查这段代码
""")

        skill = SkillLoader.load(skill_file)

        assert skill.name == "Code Review"
        assert "Review code" in skill.description
        assert "代码审查" in skill.triggers
        assert "review" in skill.triggers
        assert len(skill.steps) == 3
        assert skill.path == skill_file

    def test_load_skill_english(self, tmp_path: Path):
        """测试加载英文技能文件"""
        skill_file = tmp_path / "debug.md"
        skill_file.write_text("""# Debug

## Description
Help debug code issues.

## Triggers
- debug
- 错误

## Steps
1. Analyze error
2. Find root cause
3. Suggest fix

## Examples
- Debug this error
""")

        skill = SkillLoader.load(skill_file)

        assert skill.name == "Debug"
        assert "debug" in skill.triggers
        assert "错误" in skill.triggers

    def test_load_skill_minimal(self, tmp_path: Path):
        """测试加载最小技能文件"""
        skill_file = tmp_path / "minimal.md"
        skill_file.write_text("""# Minimal Skill

Just a description.
""")

        skill = SkillLoader.load(skill_file)

        assert skill.name == "Minimal Skill"
        assert skill.triggers == []
        assert skill.steps == []

    def test_discover_skill_files_subdir(self, tmp_path: Path):
        """测试发现技能文件 - 子目录形式"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # 创建子目录形式的技能
        review_dir = skills_dir / "code_review"
        review_dir.mkdir()
        (review_dir / "SKILL.md").write_text("# Code Review")

        debug_dir = skills_dir / "debug"
        debug_dir.mkdir()
        (debug_dir / "SKILL.md").write_text("# Debug")

        files = SkillLoader.discover(skills_dir)

        assert len(files) == 2
        names = [f.parent.name for f in files]
        assert "code_review" in names
        assert "debug" in names

    def test_discover_skill_files_skill_md(self, tmp_path: Path):
        """测试发现技能文件 - .skill.md 形式"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        (skills_dir / "review.skill.md").write_text("# Review")
        (skills_dir / "debug.skill.md").write_text("# Debug")

        files = SkillLoader.discover(skills_dir)

        assert len(files) == 2

    def test_discover_skill_files_regular_md(self, tmp_path: Path):
        """测试发现技能文件 - 普通 .md 文件"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        (skills_dir / "my_skill.md").write_text("# My Skill")

        files = SkillLoader.discover(skills_dir)

        assert len(files) == 1
        assert files[0].stem == "my_skill"

    def test_discover_no_directory(self, tmp_path: Path):
        """测试发现技能文件 - 目录不存在"""
        non_existent = tmp_path / "non_existent"
        files = SkillLoader.discover(non_existent)
        assert files == []


class TestSkillRegistry:
    """技能注册表测试"""

    def test_registry_creation(self):
        """测试注册表创建"""
        registry = SkillRegistry()
        assert registry._skills == {}

    def test_register(self):
        """测试注册技能"""
        registry = SkillRegistry()
        skill = Skill(name="Test", description="Test skill")

        registry.register(skill)

        assert "Test" in registry._skills
        assert registry._skills["Test"] == skill

    def test_unregister(self):
        """测试注销技能"""
        registry = SkillRegistry()
        skill = Skill(name="Test", description="Test skill")

        registry.register(skill)
        result = registry.unregister("Test")

        assert result is True
        assert "Test" not in registry._skills

    def test_unregister_not_found(self):
        """测试注销不存在的技能"""
        registry = SkillRegistry()
        result = registry.unregister("NonExistent")
        assert result is False

    def test_get(self):
        """测试获取技能"""
        registry = SkillRegistry()
        skill = Skill(name="Test", description="Test skill")

        registry.register(skill)
        found = registry.get("Test")

        assert found == skill

    def test_get_not_found(self):
        """测试获取不存在的技能"""
        registry = SkillRegistry()
        found = registry.get("NonExistent")
        assert found is None

    def test_list(self):
        """测试列出所有技能"""
        registry = SkillRegistry()
        skill1 = Skill(name="Skill1", description="Skill 1")
        skill2 = Skill(name="Skill2", description="Skill 2")

        registry.register(skill1)
        registry.register(skill2)

        skills = registry.list()

        assert len(skills) == 2
        assert skill1 in skills
        assert skill2 in skills

    def test_find_matching(self):
        """测试查找匹配技能"""
        registry = SkillRegistry()
        skill1 = Skill(
            name="Review",
            description="Code review",
            triggers=["review", "审查"]
        )
        skill2 = Skill(
            name="Debug",
            description="Debug code",
            triggers=["debug", "错误"]
        )

        registry.register(skill1)
        registry.register(skill2)

        matches = registry.find_matching("Please review this code")
        assert len(matches) == 1
        assert matches[0] == skill1

        matches = registry.find_matching("Help debug this error")
        assert len(matches) == 1
        assert matches[0] == skill2

    def test_find_matching_multiple(self):
        """测试查找多个匹配技能"""
        registry = SkillRegistry()
        skill1 = Skill(
            name="Review",
            description="Code review",
            triggers=["code"]
        )
        skill2 = Skill(
            name="Analyze",
            description="Code analysis",
            triggers=["code"]
        )

        registry.register(skill1)
        registry.register(skill2)

        matches = registry.find_matching("Analyze this code")
        assert len(matches) == 2

    def test_find_matching_none(self):
        """测试无匹配技能"""
        registry = SkillRegistry()
        skill = Skill(
            name="Review",
            description="Code review",
            triggers=["review"]
        )

        registry.register(skill)

        matches = registry.find_matching("Hello world")
        assert matches == []

    def test_to_system_prompt(self):
        """测试生成系统提示"""
        registry = SkillRegistry()
        skill = Skill(
            name="Review",
            description="Code review skill",
            triggers=["review"],
            steps=["Read code", "Find issues"]
        )

        registry.register(skill)

        prompt = registry.to_system_prompt()

        assert "# 可用技能" in prompt
        assert "## Review" in prompt
        assert "Code review skill" in prompt
        assert "触发词: review" in prompt
        assert "步骤:" in prompt

    def test_to_system_prompt_empty(self):
        """测试空注册表的系统提示"""
        registry = SkillRegistry()
        prompt = registry.to_system_prompt()
        assert prompt == ""

    def test_load_from_directory(self, tmp_path: Path):
        """测试从目录加载技能"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        (skills_dir / "skill1.md").write_text("""# Skill1

## 描述
First skill

## 触发
- test1
""")

        (skills_dir / "skill2.md").write_text("""# Skill2

## 描述
Second skill

## 触发
- test2
""")

        registry = SkillRegistry()
        count = registry.load_from_directory(skills_dir)

        assert count == 2
        assert registry.get("Skill1") is not None
        assert registry.get("Skill2") is not None

    def test_load_from_directory_with_errors(self, tmp_path: Path):
        """测试从目录加载技能 - 有错误"""
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        # 有效技能
        (skills_dir / "valid.md").write_text("# Valid\n\n## 描述\nValid skill")

        # 无效技能（空的，不应该导致崩溃）
        (skills_dir / "invalid.md").write_text("")

        registry = SkillRegistry()
        count = registry.load_from_directory(skills_dir)

        # 至少应该加载一个
        assert count >= 1
        assert registry.get("Valid") is not None

    def test_load_from_nonexistent_directory(self, tmp_path: Path):
        """测试从不存在的目录加载"""
        registry = SkillRegistry()
        count = registry.load_from_directory(tmp_path / "nonexistent")
        assert count == 0

    def test_clear(self):
        """测试清除所有技能"""
        registry = SkillRegistry()
        registry.register(Skill(name="Skill1", description=""))
        registry.register(Skill(name="Skill2", description=""))

        registry.clear()

        assert len(registry._skills) == 0


class TestGlobalRegistry:
    """全局注册表测试"""

    def test_get_skill_registry(self):
        """测试获取全局注册表"""
        # 重置全局注册表
        import pi_python.skills.registry as reg_module
        reg_module._global_registry = None

        registry = get_skill_registry()

        assert isinstance(registry, SkillRegistry)
        # 应该包含内置技能
        skills = registry.list()
        assert len(skills) > 0

    def test_register_skill_global(self):
        """测试全局注册技能"""
        # 重置全局注册表
        import pi_python.skills.registry as reg_module
        reg_module._global_registry = None

        skill = Skill(name="GlobalTest", description="Global test skill")
        register_skill(skill)

        registry = get_skill_registry()
        assert registry.get("GlobalTest") == skill

    def test_find_skills_global(self):
        """测试全局查找技能"""
        # 重置全局注册表
        import pi_python.skills.registry as reg_module
        reg_module._global_registry = None

        # 内置技能应该包含 debug
        matches = find_skills("debug this error")

        # 应该找到 debug 技能
        assert len(matches) >= 1
        assert any("debug" in s.name.lower() for s in matches)


class TestBuiltinSkills:
    """内置技能测试"""

    def test_create_builtin_skills(self):
        """测试创建内置技能"""
        skills = create_builtin_skills()

        assert isinstance(skills, list)
        assert len(skills) == 3

        names = [s.name for s in skills]
        assert "Code Review" in names
        assert "Debug" in names
        assert "Generate Documentation" in names

    def test_code_review_skill(self):
        """测试代码审查技能"""
        skills = create_builtin_skills()
        review_skill = next(s for s in skills if s.name == "Code Review")

        assert "代码审查" in review_skill.triggers
        assert "review" in review_skill.triggers
        assert len(review_skill.steps) == 5
        assert review_skill.matches("Review this code") is True

    def test_debug_skill(self):
        """测试调试技能"""
        skills = create_builtin_skills()
        debug_skill = next(s for s in skills if s.name == "Debug")

        assert "调试" in debug_skill.triggers
        assert "debug" in debug_skill.triggers
        assert "报错" in debug_skill.triggers
        assert debug_skill.matches("debug this error") is True

    def test_docs_skill(self):
        """测试文档生成技能"""
        skills = create_builtin_skills()
        docs_skill = next(s for s in skills if s.name == "Generate Documentation")

        assert "生成文档" in docs_skill.triggers
        assert "documentation" in docs_skill.triggers
        assert docs_skill.matches("Generate documentation for this") is True
        assert docs_skill.matches("Add docstring to this function") is True


class TestSkillIntegration:
    """技能集成测试"""

    def test_full_skill_workflow(self, tmp_path: Path):
        """测试完整技能工作流"""
        # 1. 创建技能文件
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        skill_file = skills_dir / "my_workflow.md"
        skill_file.write_text("""# My Workflow

## 描述
A custom workflow skill.

## 触发
- workflow
- 工作流

## 步骤
1. Initialize
2. Process
3. Finalize

## 示例
- Run the workflow
- 执行工作流
""")

        # 2. 加载技能
        skill = SkillLoader.load(skill_file)
        assert skill.name == "My Workflow"

        # 3. 注册到注册表
        registry = SkillRegistry()
        registry.register(skill)

        # 4. 查找匹配
        matches = registry.find_matching("Run the workflow")
        assert len(matches) == 1
        assert matches[0].name == "My Workflow"

        # 5. 生成系统提示
        prompt = registry.to_system_prompt()
        assert "My Workflow" in prompt
        assert "workflow" in prompt

    def test_skill_with_special_characters(self, tmp_path: Path):
        """测试包含特殊字符的技能"""
        skill_file = tmp_path / "special.md"
        skill_file.write_text("""# Special Skill! @#$%

## 描述
Skill with special characters: 中文描述 🎉

## 触发
- special!
- 特殊@字符

## 步骤
1. Step with emoji 🚀
2. 中文步骤

## 示例
- Test with special chars
""")

        skill = SkillLoader.load(skill_file)

        assert skill.name == "Special Skill! @#$%"
        assert "中文描述" in skill.description
        assert len(skill.steps) == 2