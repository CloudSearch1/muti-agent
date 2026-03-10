"""
Skills API 测试

测试 Skills CRUD API 端点，包括：
- 模型验证测试
- API 端点测试
- 边界情况测试
- 安全性测试
- 并发安全测试
"""

from __future__ import annotations

import asyncio
import threading
from datetime import datetime
from typing import Any

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI

from src.api.routes.skill import (
    SkillBase,
    SkillCreate,
    SkillUpdate,
    SkillResponse,
    SkillListResponse,
    SkillStorage,
    router,
    VALID_CATEGORIES,
    SKILL_NAME_PATTERN,
)


# ============ 模型测试 ============


class TestSkillModels:
    """Skill 模型测试"""

    def test_skill_base_defaults(self):
        """测试 SkillBase 默认值"""
        skill = SkillBase(name="test-skill")
        assert skill.name == "test-skill"
        assert skill.description == ""
        assert skill.category == "general"
        assert skill.version == "1.0.0"
        assert skill.config == {}
        assert skill.enabled is True

    def test_skill_base_custom_values(self):
        """测试 SkillBase 自定义值"""
        skill = SkillBase(
            name="custom-skill",
            description="A custom skill",
            category="api",
            version="2.0.0",
            config={"key": "value"},
            enabled=False
        )
        assert skill.name == "custom-skill"
        assert skill.description == "A custom skill"
        assert skill.category == "api"
        assert skill.version == "2.0.0"
        assert skill.config == {"key": "value"}
        assert skill.enabled is False

    def test_skill_create(self):
        """测试 SkillCreate"""
        create = SkillCreate(name="new-skill", description="New skill")
        assert create.name == "new-skill"
        assert create.description == "New skill"

    def test_skill_update_partial(self):
        """测试 SkillUpdate 部分更新"""
        update = SkillUpdate(enabled=False)
        assert update.enabled is False
        assert update.name is None
        assert update.description is None

    def test_skill_response(self):
        """测试 SkillResponse"""
        now = datetime.now()
        response = SkillResponse(
            id=1,
            name="test",
            description="Test skill",
            category="general",
            version="1.0.0",
            config={},
            enabled=True,
            created_at=now,
            updated_at=now
        )
        assert response.id == 1
        assert response.name == "test"
        assert response.enabled is True

    def test_skill_list_response(self):
        """测试 SkillListResponse"""
        now = datetime.now()
        items = [
            SkillResponse(
                id=1, name="skill1", description="", category="general",
                version="1.0.0", config={}, enabled=True,
                created_at=now, updated_at=now
            ),
            SkillResponse(
                id=2, name="skill2", description="", category="api",
                version="1.0.0", config={}, enabled=False,
                created_at=now, updated_at=now
            )
        ]
        list_response = SkillListResponse(
            items=items,
            total=10,
            page=1,
            page_size=2
        )
        assert len(list_response.items) == 2
        assert list_response.total == 10
        assert list_response.page == 1


# ============ 名称验证测试 ============


class TestSkillNameValidation:
    """技能名称验证测试"""

    def test_valid_name_simple(self):
        """测试有效的简单名称"""
        skill = SkillBase(name="simplify")
        assert skill.name == "simplify"

    def test_valid_name_with_underscore(self):
        """测试带下划线的名称"""
        skill = SkillBase(name="code_generation")
        assert skill.name == "code_generation"

    def test_valid_name_with_hyphen(self):
        """测试带连字符的名称"""
        skill = SkillBase(name="claude-api")
        assert skill.name == "claude-api"

    def test_valid_name_with_numbers(self):
        """测试带数字的名称"""
        skill = SkillBase(name="api2json")
        assert skill.name == "api2json"

    def test_invalid_name_starts_with_number(self):
        """测试以数字开头的名称（无效）"""
        with pytest.raises(ValueError, match="必须以字母开头"):
            SkillBase(name="1skill")

    def test_invalid_name_starts_with_underscore(self):
        """测试以下划线开头的名称（无效）"""
        with pytest.raises(ValueError, match="必须以字母开头"):
            SkillBase(name="_skill")

    def test_invalid_name_with_spaces(self):
        """测试包含空格的名称（无效）"""
        with pytest.raises(ValueError):
            SkillBase(name="test skill")

    def test_invalid_name_with_special_chars(self):
        """测试包含特殊字符的名称（无效）"""
        with pytest.raises(ValueError):
            SkillBase(name="skill@name")

    def test_invalid_name_empty(self):
        """测试空名称"""
        with pytest.raises(ValueError):
            SkillBase(name="")

    def test_invalid_name_too_long(self):
        """测试过长的名称"""
        long_name = "a" * 101
        with pytest.raises(ValueError):
            SkillBase(name=long_name)

    def test_name_whitespace_trimmed(self):
        """测试名称空白被去除"""
        skill = SkillBase(name="  test-skill  ")
        assert skill.name == "test-skill"


# ============ 版本验证测试 ============


class TestVersionValidation:
    """版本号验证测试"""

    def test_valid_version_simple(self):
        """测试有效的简单版本号"""
        skill = SkillBase(name="test", version="1.0.0")
        assert skill.version == "1.0.0"

    def test_valid_version_with_prerelease(self):
        """测试带预发布标签的版本号"""
        skill = SkillBase(name="test", version="2.0.0-beta")
        assert skill.version == "2.0.0-beta"

    def test_valid_version_with_prerelease_number(self):
        """测试带预发布编号的版本号"""
        skill = SkillBase(name="test", version="1.2.3-rc1")
        assert skill.version == "1.2.3-rc1"

    def test_invalid_version_format(self):
        """测试无效的版本号格式"""
        with pytest.raises(ValueError, match="语义化版本"):
            SkillBase(name="test", version="1.0")

    def test_invalid_version_with_v_prefix(self):
        """测试带 v 前缀的版本号（无效）"""
        with pytest.raises(ValueError):
            SkillBase(name="test", version="v1.0.0")


# ============ 分类验证测试 ============


class TestCategoryValidation:
    """分类验证测试"""

    def test_valid_category(self):
        """测试有效的分类"""
        for category in VALID_CATEGORIES:
            skill = SkillBase(name="test", category=category)
            assert skill.category == category

    def test_custom_category_allowed(self):
        """测试自定义分类被允许（但会记录警告）"""
        skill = SkillBase(name="test", category="custom_category")
        assert skill.category == "custom_category"

    def test_category_normalized(self):
        """测试分类被规范化（小写）"""
        skill = SkillBase(name="test", category="API")
        assert skill.category == "api"


# ============ 配置验证测试 ============


class TestConfigValidation:
    """配置验证测试"""

    def test_valid_config(self):
        """测试有效的配置"""
        skill = SkillBase(
            name="test",
            config={"timeout": 30, "retries": 3}
        )
        assert skill.config == {"timeout": 30, "retries": 3}

    def test_nested_config(self):
        """测试嵌套配置"""
        skill = SkillBase(
            name="test",
            config={"nested": {"key": "value"}}
        )
        assert skill.config["nested"]["key"] == "value"

    def test_empty_config(self):
        """测试空配置"""
        skill = SkillBase(name="test", config={})
        assert skill.config == {}

    def test_config_too_large(self):
        """测试过大的配置"""
        # 创建一个超过 10000 字符的配置
        large_config = {"key_" + str(i): "x" * 500 for i in range(25)}
        with pytest.raises(ValueError, match="过大"):
            SkillBase(name="test", config=large_config)


# ============ API 端点测试 ============


class TestSkillsAPI:
    """Skills API 测试"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/skills")
        return app

    @pytest.mark.asyncio
    async def test_list_skills(self, app):
        """测试列出技能"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/skills/")
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data

    @pytest.mark.asyncio
    async def test_list_skills_with_filter(self, app):
        """测试带过滤的技能列表"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 测试分类过滤
            response = await client.get("/api/v1/skills/?category=api")
            assert response.status_code == 200

            # 测试状态过滤
            response = await client.get("/api/v1/skills/?enabled=true")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_list_skills_with_search(self, app):
        """测试带搜索的技能列表"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/skills/?search=code")
            assert response.status_code == 200
            data = response.json()
            # 验证搜索结果
            for item in data["items"]:
                assert "code" in item["name"].lower() or "code" in item["description"].lower()

    @pytest.mark.asyncio
    async def test_create_skill(self, app):
        """测试创建技能"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/skills/",
                json={
                    "name": "test-skill-new",
                    "description": "A test skill",
                    "category": "testing",
                    "version": "1.0.0"
                }
            )
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "test-skill-new"

    @pytest.mark.asyncio
    async def test_create_duplicate_skill(self, app):
        """测试创建重复技能"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 先创建一个
            await client.post(
                "/api/v1/skills/",
                json={"name": "duplicate-skill-test"}
            )
            # 再创建同名的
            response = await client.post(
                "/api/v1/skills/",
                json={"name": "duplicate-skill-test"}
            )
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_skill_invalid_name(self, app):
        """测试创建无效名称的技能"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/skills/",
                json={"name": "123invalid"}
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_skill(self, app):
        """测试获取单个技能"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 获取列表找到 ID
            list_response = await client.get("/api/v1/skills/")
            skills = list_response.json()["items"]
            if skills:
                skill_id = skills[0]["id"]
                response = await client.get(f"/api/v1/skills/{skill_id}")
                assert response.status_code == 200
                data = response.json()
                assert data["id"] == skill_id

    @pytest.mark.asyncio
    async def test_get_nonexistent_skill(self, app):
        """测试获取不存在的技能"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/skills/99999")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_skill_invalid_id(self, app):
        """测试获取无效 ID 的技能"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/skills/0")
            assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_skill(self, app):
        """测试更新技能"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 创建一个技能
            create_response = await client.post(
                "/api/v1/skills/",
                json={"name": "skill-to-update-test"}
            )
            skill_id = create_response.json()["id"]

            # 更新技能
            response = await client.put(
                f"/api/v1/skills/{skill_id}",
                json={"description": "Updated description"}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_skill_no_changes(self, app):
        """测试无更改的更新请求"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 创建一个技能
            create_response = await client.post(
                "/api/v1/skills/",
                json={"name": "skill-no-change-test"}
            )
            skill_id = create_response.json()["id"]

            # 空更新
            response = await client.put(
                f"/api/v1/skills/{skill_id}",
                json={}
            )
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_update_nonexistent_skill(self, app):
        """测试更新不存在的技能"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.put(
                "/api/v1/skills/99999",
                json={"name": "updated"}
            )
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_skill(self, app):
        """测试删除技能"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 创建一个技能
            create_response = await client.post(
                "/api/v1/skills/",
                json={"name": "skill-to-delete-test"}
            )
            skill_id = create_response.json()["id"]

            # 删除技能
            response = await client.delete(f"/api/v1/skills/{skill_id}")
            assert response.status_code == 204

            # 验证已删除
            get_response = await client.get(f"/api/v1/skills/{skill_id}")
            assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_skill(self, app):
        """测试删除不存在的技能"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/skills/99999")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_categories(self, app):
        """测试获取分类列表"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/skills/categories")
            assert response.status_code == 200
            categories = response.json()
            assert isinstance(categories, list)

    @pytest.mark.asyncio
    async def test_toggle_skill_status(self, app):
        """测试切换技能状态"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 创建一个技能
            create_response = await client.post(
                "/api/v1/skills/",
                json={"name": "toggle-skill-test", "enabled": True}
            )
            skill_id = create_response.json()["id"]
            original_status = create_response.json()["enabled"]

            # 切换状态
            response = await client.patch(f"/api/v1/skills/{skill_id}/toggle")
            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] != original_status


# ============ 边界情况测试 ============


class TestSkillsEdgeCases:
    """Skills 边界情况测试"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/skills")
        return app

    def test_skill_name_min_length(self):
        """测试技能名称最小长度"""
        with pytest.raises(ValueError):
            SkillBase(name="")

    def test_skill_name_max_length(self):
        """测试技能名称最大长度"""
        long_name = "a" * 101
        with pytest.raises(ValueError):
            SkillBase(name=long_name)

    def test_skill_description_max_length(self):
        """测试描述最大长度"""
        long_desc = "a" * 1001
        with pytest.raises(ValueError):
            SkillBase(name="test", description=long_desc)

    @pytest.mark.asyncio
    async def test_list_skills_pagination(self, app):
        """测试技能列表分页"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/skills/?page=1&page_size=2")
            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 1
            assert data["page_size"] == 2

    @pytest.mark.asyncio
    async def test_pagination_bounds(self, app):
        """测试分页边界"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # page_size 最小值
            response = await client.get("/api/v1/skills/?page=1&page_size=1")
            assert response.status_code == 200

            # page_size 最大值
            response = await client.get("/api/v1/skills/?page=1&page_size=100")
            assert response.status_code == 200

            # 超出范围的 page_size
            response = await client.get("/api/v1/skills/?page=1&page_size=101")
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_skill_with_config(self, app):
        """测试带配置创建技能"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/skills/",
                json={
                    "name": "skill-with-config-test",
                    "config": {
                        "option1": "value1",
                        "nested": {"key": "value"}
                    }
                }
            )
            assert response.status_code == 201
            data = response.json()
            assert data["config"]["option1"] == "value1"

    @pytest.mark.asyncio
    async def test_update_skill_name_conflict(self, app):
        """测试更新时名称冲突"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 创建两个技能
            await client.post(
                "/api/v1/skills/",
                json={"name": "skill-a-conflict-test"}
            )
            response = await client.post(
                "/api/v1/skills/",
                json={"name": "skill-b-conflict-test"}
            )
            skill_b_id = response.json()["id"]

            # 尝试将 skill-b 改名为 skill-a
            response = await client.put(
                f"/api/v1/skills/{skill_b_id}",
                json={"name": "skill-a-conflict-test"}
            )
            assert response.status_code == 400


# ============ 并发安全测试 ============


class TestConcurrentAccess:
    """并发访问测试"""

    def test_storage_thread_safety(self):
        """测试存储线程安全性"""
        storage = SkillStorage()
        errors: list[Exception] = []
        success_count = 0
        lock = threading.Lock()

        def create_skill(name: str) -> None:
            nonlocal success_count
            try:
                now = datetime.now()
                skill_data = {
                    "name": name,
                    "description": f"Skill {name}",
                    "category": "general",
                    "version": "1.0.0",
                    "config": {},
                    "enabled": True,
                    "created_at": now,
                    "updated_at": now,
                }
                storage.create(skill_data)
                with lock:
                    success_count += 1
            except Exception as e:
                with lock:
                    errors.append(e)

        # 创建多个线程同时创建技能
        threads = []
        for i in range(10):
            t = threading.Thread(target=create_skill, args=(f"concurrent-skill-{i}",))
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 验证所有技能都被创建
        assert success_count == 10
        assert len(errors) == 0

    def test_storage_duplicate_prevention(self):
        """测试并发时防止重复名称"""
        storage = SkillStorage()
        errors: list[Exception] = []
        created_count = 0
        lock = threading.Lock()

        def try_create_same_name() -> None:
            nonlocal created_count
            try:
                now = datetime.now()
                skill_data = {
                    "name": "same-name-skill",
                    "description": "Same name",
                    "category": "general",
                    "version": "1.0.0",
                    "config": {},
                    "enabled": True,
                    "created_at": now,
                    "updated_at": now,
                }
                storage.create(skill_data)
                with lock:
                    created_count += 1
            except ValueError:
                pass  # 预期的错误

        # 多个线程尝试创建同名技能
        threads = []
        for _ in range(5):
            t = threading.Thread(target=try_create_same_name)
            threads.append(t)

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # 只应该有一个成功创建
        assert created_count == 1


# ============ SkillStorage 单元测试 ============


class TestSkillStorage:
    """SkillStorage 单元测试"""

    def test_create_and_get(self):
        """测试创建和获取"""
        storage = SkillStorage()
        now = datetime.now()
        skill_data = {
            "name": "test-skill",
            "description": "Test",
            "category": "general",
            "version": "1.0.0",
            "config": {},
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        }

        skill_id = storage.create(skill_data.copy())
        assert skill_id == 1

        retrieved = storage.get(skill_id)
        assert retrieved is not None
        assert retrieved["name"] == "test-skill"

    def test_get_by_name(self):
        """测试按名称获取"""
        storage = SkillStorage()
        now = datetime.now()
        skill_data = {
            "name": "unique-name-skill",
            "description": "Test",
            "category": "general",
            "version": "1.0.0",
            "config": {},
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        }

        storage.create(skill_data.copy())
        retrieved = storage.get_by_name("unique-name-skill")
        assert retrieved is not None
        assert retrieved["name"] == "unique-name-skill"

        # 不存在的名称
        assert storage.get_by_name("nonexistent") is None

    def test_update(self):
        """测试更新"""
        storage = SkillStorage()
        now = datetime.now()
        skill_data = {
            "name": "update-test-skill",
            "description": "Original",
            "category": "general",
            "version": "1.0.0",
            "config": {},
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        }

        skill_id = storage.create(skill_data.copy())

        # 更新
        success = storage.update(skill_id, {"description": "Updated"})
        assert success is True

        updated = storage.get(skill_id)
        assert updated["description"] == "Updated"

    def test_update_nonexistent(self):
        """测试更新不存在的技能"""
        storage = SkillStorage()
        success = storage.update(999, {"description": "Updated"})
        assert success is False

    def test_delete(self):
        """测试删除"""
        storage = SkillStorage()
        now = datetime.now()
        skill_data = {
            "name": "delete-test-skill",
            "description": "Test",
            "category": "general",
            "version": "1.0.0",
            "config": {},
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        }

        skill_id = storage.create(skill_data.copy())
        assert storage.get(skill_id) is not None

        # 删除
        success = storage.delete(skill_id)
        assert success is True
        assert storage.get(skill_id) is None

        # 再次删除
        success = storage.delete(skill_id)
        assert success is False

    def test_list_all(self):
        """测试列出所有技能"""
        storage = SkillStorage()
        now = datetime.now()

        for i in range(3):
            skill_data = {
                "name": f"list-skill-{i}",
                "description": f"Skill {i}",
                "category": "general",
                "version": "1.0.0",
                "config": {},
                "enabled": True,
                "created_at": now,
                "updated_at": now,
            }
            storage.create(skill_data.copy())

        all_skills = storage.list_all()
        assert len(all_skills) == 3

    def test_count(self):
        """测试计数"""
        storage = SkillStorage()
        assert storage.count() == 0

        now = datetime.now()
        skill_data = {
            "name": "count-skill",
            "description": "Test",
            "category": "general",
            "version": "1.0.0",
            "config": {},
            "enabled": True,
            "created_at": now,
            "updated_at": now,
        }
        storage.create(skill_data.copy())
        assert storage.count() == 1


# ============ 安全性测试 ============


class TestSecurity:
    """安全性测试"""

    @pytest.fixture
    def app(self):
        """创建测试应用"""
        app = FastAPI()
        app.include_router(router, prefix="/api/v1/skills")
        return app

    @pytest.mark.asyncio
    async def test_sql_injection_prevention(self, app):
        """测试 SQL 注入防护（名称验证）"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 尝试注入
            response = await client.post(
                "/api/v1/skills/",
                json={"name": "'; DROP TABLE skills; --"}
            )
            # 应该被验证器拒绝
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_xss_in_description(self, app):
        """测试 XSS 防护（描述中的脚本）"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/skills/",
                json={
                    "name": "xss-test-skill",
                    "description": "<script>alert('xss')</script>"
                }
            )
            # API 应该接受（因为是 JSON），但前端需要处理
            assert response.status_code == 201
            # 验证描述被存储
            data = response.json()
            assert "<script>" in data["description"]

    @pytest.mark.asyncio
    async def test_large_payload_rejection(self, app):
        """测试大负载拒绝"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 超大配置
            large_config = {f"key_{i}": "x" * 100 for i in range(200)}
            response = await client.post(
                "/api/v1/skills/",
                json={
                    "name": "large-config-skill",
                    "config": large_config
                }
            )
            assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_search_injection(self, app):
        """测试搜索参数注入"""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 搜索参数应该被安全处理
            response = await client.get("/api/v1/skills/?search=<script>")
            assert response.status_code == 200

            response = await client.get("/api/v1/skills/?search='; DROP TABLE --")
            assert response.status_code == 200