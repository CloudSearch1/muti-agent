"""
Skill 路由模块

提供 Skill 管理相关的 API 端点，包括 CRUD 操作和分类管理。

功能:
- 技能的创建、读取、更新、删除 (CRUD)
- 技能分类管理
- 技能状态切换
- 分页查询和过滤

安全特性:
- 输入验证和清洗
- 名称规范化防止注入
- 线程安全的数据存储
"""

from __future__ import annotations

import re
import threading
from datetime import datetime
from typing import Any

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

logger = structlog.get_logger(__name__)

router = APIRouter()


# ===========================================
# 常量定义
# ===========================================

# 名称验证正则：只允许字母、数字、下划线和连字符
SKILL_NAME_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$")

# 允许的分类列表
VALID_CATEGORIES = frozenset([
    "general",
    "code_review",
    "api",
    "generation",
    "docs",
    "testing",
    "automation",
    "integration",
])

# 版本号验证正则
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9]+)?$")


# ===========================================
# 请求/响应模型
# ===========================================


class SkillBase(BaseModel):
    """Skill 基础模型

    用于定义技能的基本属性，包含输入验证。

    Attributes:
        name: 技能名称，唯一标识符
        description: 技能描述
        category: 技能分类
        version: 版本号，遵循语义化版本规范
        config: 配置信息字典
        enabled: 是否启用
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="技能名称，唯一标识符",
        examples=["code-review"],
    )
    description: str = Field(
        default="",
        max_length=1000,
        description="技能描述",
        examples=["Review code for quality issues"],
    )
    category: str = Field(
        default="general",
        max_length=50,
        description="技能分类",
        examples=["code_review"],
    )
    version: str = Field(
        default="1.0.0",
        max_length=20,
        description="版本号，遵循语义化版本规范",
        examples=["1.2.3"],
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="配置信息",
        examples=[{"timeout": 30, "retries": 3}],
    )
    enabled: bool = Field(
        default=True,
        description="是否启用",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """验证技能名称格式

        Args:
            v: 待验证的名称

        Returns:
            清洗后的名称

        Raises:
            ValueError: 名称格式不合法
        """
        # 清洗：去除首尾空白
        name = v.strip()

        # 长度检查
        if not 1 <= len(name) <= 100:
            raise ValueError("技能名称长度必须在 1-100 个字符之间")

        # 格式检查：只允许字母、数字、下划线和连字符，必须以字母开头
        if not SKILL_NAME_PATTERN.match(name):
            raise ValueError(
                "技能名称必须以字母开头，只能包含字母、数字、下划线和连字符"
            )

        return name

    @field_validator("category")
    @classmethod
    def validate_category(cls, v: str) -> str:
        """验证技能分类

        Args:
            v: 待验证的分类

        Returns:
            清洗后的分类

        Raises:
            ValueError: 分类不在允许列表中
        """
        category = v.strip().lower()
        if category not in VALID_CATEGORIES:
            # 允许自定义分类，但记录警告
            logger.warning(
                "Using custom category",
                category=category,
                valid_categories=list(VALID_CATEGORIES),
            )
        return category

    @field_validator("version")
    @classmethod
    def validate_version(cls, v: str) -> str:
        """验证版本号格式

        Args:
            v: 待验证的版本号

        Returns:
            清洗后的版本号

        Raises:
            ValueError: 版本号格式不合法
        """
        version = v.strip()
        if not VERSION_PATTERN.match(version):
            raise ValueError(
                "版本号必须遵循语义化版本规范，如 1.0.0 或 1.0.0-beta"
            )
        return version

    @field_validator("config")
    @classmethod
    def validate_config(cls, v: dict[str, Any]) -> dict[str, Any]:
        """验证配置字典

        Args:
            v: 待验证的配置字典

        Returns:
            验证后的配置字典

        Raises:
            ValueError: 配置包含不安全的内容
        """
        # 检查配置大小
        if len(str(v)) > 10000:
            raise ValueError("配置信息过大，最大 10000 字符")

        # 检查敏感键名（防止注入敏感配置）
        sensitive_keys = {"password", "secret", "token", "key", "credential"}
        for key in v:
            if key.lower() in sensitive_keys:
                logger.warning(
                    "Config contains potentially sensitive key",
                    key=key,
                )

        return v


class SkillCreate(SkillBase):
    """Skill 创建请求模型

    继承 SkillBase 的所有属性和验证规则。
    """

    pass


class SkillUpdate(BaseModel):
    """Skill 更新请求模型

    所有字段均为可选，支持部分更新。

    Attributes:
        name: 新的技能名称
        description: 新的描述
        category: 新的分类
        version: 新的版本号
        config: 新的配置
        enabled: 新的启用状态
    """

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    category: str | None = Field(None, max_length=50)
    version: str | None = Field(None, max_length=20)
    config: dict[str, Any] | None = None
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        """验证技能名称格式"""
        if v is None:
            return None
        name = v.strip()
        if not 1 <= len(name) <= 100:
            raise ValueError("技能名称长度必须在 1-100 个字符之间")
        if not SKILL_NAME_PATTERN.match(name):
            raise ValueError(
                "技能名称必须以字母开头，只能包含字母、数字、下划线和连字符"
            )
        return name


class SkillResponse(BaseModel):
    """Skill 响应模型

    包含技能的完整信息，包括系统生成的字段。

    Attributes:
        id: 技能唯一 ID
        name: 技能名称
        description: 技能描述
        category: 技能分类
        version: 版本号
        config: 配置信息
        enabled: 是否启用
        created_at: 创建时间
        updated_at: 最后更新时间
    """

    id: int
    name: str
    description: str
    category: str
    version: str
    config: dict[str, Any]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class SkillListResponse(BaseModel):
    """Skill 列表响应模型

    包含分页信息和技能列表。

    Attributes:
        items: 技能列表
        total: 总数量
        page: 当前页码
        page_size: 每页数量
    """

    items: list[SkillResponse]
    total: int
    page: int
    page_size: int


class SkillErrorResponse(BaseModel):
    """错误响应模型"""

    detail: str
    error_code: str | None = None


# ===========================================
# 线程安全的数据存储
# ===========================================

class SkillStorage:
    """线程安全的技能存储

    使用锁保护数据操作，确保并发安全。

    Attributes:
        _skills: 技能数据字典
        _counter: ID 计数器
        _lock: 线程锁
    """

    def __init__(self) -> None:
        """初始化存储"""
        self._skills: dict[int, dict[str, Any]] = {}
        self._counter: int = 0
        self._lock: threading.Lock = threading.Lock()
        self._name_index: dict[str, int] = {}  # 名称索引，用于快速查找

    def get_next_id(self) -> int:
        """获取下一个 ID（线程安全）"""
        with self._lock:
            self._counter += 1
            return self._counter

    def create(self, skill_data: dict[str, Any]) -> int:
        """创建技能（线程安全）

        Args:
            skill_data: 技能数据

        Returns:
            新技能的 ID

        Raises:
            ValueError: 名称已存在
        """
        with self._lock:
            name = skill_data["name"]
            if name in self._name_index:
                raise ValueError(f"Skill with name '{name}' already exists")

            skill_id = self._counter + 1
            self._counter = skill_id

            skill_data["id"] = skill_id
            self._skills[skill_id] = skill_data
            self._name_index[name] = skill_id

            return skill_id

    def get(self, skill_id: int) -> dict[str, Any] | None:
        """获取技能"""
        return self._skills.get(skill_id)

    def get_by_name(self, name: str) -> dict[str, Any] | None:
        """通过名称获取技能"""
        skill_id = self._name_index.get(name)
        if skill_id is not None:
            return self._skills.get(skill_id)
        return None

    def update(self, skill_id: int, updates: dict[str, Any]) -> bool:
        """更新技能（线程安全）

        Args:
            skill_id: 技能 ID
            updates: 更新数据

        Returns:
            是否更新成功
        """
        with self._lock:
            if skill_id not in self._skills:
                return False

            skill = self._skills[skill_id]
            old_name = skill.get("name")

            # 如果更新名称，需要更新索引
            if "name" in updates and updates["name"] != old_name:
                new_name = updates["name"]
                if new_name in self._name_index:
                    return False  # 新名称已存在
                del self._name_index[old_name]
                self._name_index[new_name] = skill_id

            skill.update(updates)
            return True

    def delete(self, skill_id: int) -> bool:
        """删除技能（线程安全）"""
        with self._lock:
            if skill_id not in self._skills:
                return False

            skill = self._skills[skill_id]
            name = skill.get("name")
            if name in self._name_index:
                del self._name_index[name]
            del self._skills[skill_id]
            return True

    def list_all(self) -> list[dict[str, Any]]:
        """获取所有技能"""
        return list(self._skills.values())

    def count(self) -> int:
        """获取技能总数"""
        return len(self._skills)


# 全局存储实例
_storage = SkillStorage()


def _init_default_skills() -> None:
    """初始化默认技能数据"""
    if _storage.count() > 0:
        return

    default_skills = [
        {
            "name": "simplify",
            "description": "Review changed code for reuse, quality, and efficiency, then fix any issues found.",
            "category": "code_review",
            "version": "1.0.0",
            "config": {"auto_fix": True, "max_lines": 500},
            "enabled": True,
        },
        {
            "name": "claude-api",
            "description": "Build apps with the Claude API or Anthropic SDK.",
            "category": "api",
            "version": "1.0.0",
            "config": {"model": "claude-sonnet-4-6", "max_tokens": 4096},
            "enabled": True,
        },
        {
            "name": "code-generation",
            "description": "Generate code from natural language descriptions.",
            "category": "generation",
            "version": "1.2.0",
            "config": {"language": "python", "style": "pep8"},
            "enabled": True,
        },
        {
            "name": "documentation",
            "description": "Generate documentation for code files.",
            "category": "docs",
            "version": "1.0.0",
            "config": {"format": "markdown", "include_examples": True},
            "enabled": True,
        },
        {
            "name": "testing",
            "description": "Generate and run tests for code.",
            "category": "testing",
            "version": "1.1.0",
            "config": {"framework": "pytest", "coverage_threshold": 80},
            "enabled": False,
        },
    ]

    now = datetime.now()
    for skill_data in default_skills:
        skill_data["created_at"] = now
        skill_data["updated_at"] = now
        try:
            _storage.create(skill_data.copy())
        except ValueError as e:
            logger.warning("Failed to create default skill", error=str(e))


# 初始化默认数据
_init_default_skills()


# ===========================================
# 辅助函数
# ===========================================


def _build_skill_response(skill_data: dict[str, Any]) -> SkillResponse:
    """构建 Skill 响应对象

    Args:
        skill_data: 技能数据字典

    Returns:
        SkillResponse 对象
    """
    return SkillResponse(
        id=skill_data["id"],
        name=skill_data["name"],
        description=skill_data["description"],
        category=skill_data["category"],
        version=skill_data["version"],
        config=skill_data["config"],
        enabled=skill_data["enabled"],
        created_at=skill_data["created_at"],
        updated_at=skill_data["updated_at"],
    )


# ===========================================
# API 端点
# ===========================================


@router.get(
    "/",
    response_model=SkillListResponse,
    summary="列出所有 Skills",
    description="获取技能列表，支持分类过滤、状态过滤和分页。",
)
async def list_skills(
    category: str | None = Query(
        None,
        description="按分类过滤",
        examples=["code_review"],
    ),
    enabled: bool | None = Query(
        None,
        description="按启用状态过滤",
    ),
    search: str | None = Query(
        None,
        description="搜索关键词（匹配名称和描述）",
        max_length=100,
    ),
    page: int = Query(
        1,
        ge=1,
        description="页码",
    ),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="每页数量",
    ),
) -> SkillListResponse:
    """获取 Skill 列表

    支持多条件过滤和分页查询。

    Args:
        category: 分类过滤条件
        enabled: 启用状态过滤条件
        search: 搜索关键词
        page: 页码（从 1 开始）
        page_size: 每页数量（1-100）

    Returns:
        SkillListResponse: 分页的技能列表
    """
    skills = _storage.list_all()

    # 分类过滤
    if category:
        category_lower = category.lower().strip()
        skills = [s for s in skills if s["category"] == category_lower]

    # 启用状态过滤
    if enabled is not None:
        skills = [s for s in skills if s["enabled"] == enabled]

    # 搜索过滤
    if search:
        search_lower = search.lower().strip()
        skills = [
            s
            for s in skills
            if search_lower in s["name"].lower()
            or search_lower in s["description"].lower()
        ]

    # 排序（按 ID 升序）
    skills.sort(key=lambda x: x["id"])

    # 分页
    total = len(skills)
    start = (page - 1) * page_size
    end = start + page_size
    items = skills[start:end]

    logger.debug(
        "Listed skills",
        total=total,
        page=page,
        page_size=page_size,
        filters={"category": category, "enabled": enabled, "search": search},
    )

    return SkillListResponse(
        items=[_build_skill_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/",
    response_model=SkillResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建 Skill",
    description="创建新的技能。名称必须唯一。",
    responses={
        201: {"description": "创建成功"},
        400: {"model": SkillErrorResponse, "description": "名称已存在或数据验证失败"},
        422: {"model": SkillErrorResponse, "description": "请求数据格式错误"},
    },
)
async def create_skill(skill: SkillCreate) -> SkillResponse:
    """创建新的 Skill

    Args:
        skill: 技能创建请求

    Returns:
        SkillResponse: 创建的技能信息

    Raises:
        HTTPException: 名称已存在时返回 400
    """
    # 检查名称是否已存在
    existing = _storage.get_by_name(skill.name)
    if existing:
        logger.warning(
            "Attempted to create skill with existing name",
            name=skill.name,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Skill with name '{skill.name}' already exists",
        )

    now = datetime.now()
    skill_data = {
        "name": skill.name,
        "description": skill.description,
        "category": skill.category,
        "version": skill.version,
        "config": skill.config,
        "enabled": skill.enabled,
        "created_at": now,
        "updated_at": now,
    }

    try:
        skill_id = _storage.create(skill_data)
        skill_data["id"] = skill_id
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    logger.info("Skill created", skill_id=skill_id, name=skill.name)
    return _build_skill_response(skill_data)


@router.get(
    "/categories",
    response_model=list[str],
    summary="获取所有分类",
    description="获取系统中所有可用的技能分类。",
)
async def get_categories() -> list[str]:
    """获取所有 Skill 分类

    Returns:
        list[str]: 排序后的分类列表
    """
    skills = _storage.list_all()
    categories = {s["category"] for s in skills}
    return sorted(categories)


@router.get(
    "/{skill_id}",
    response_model=SkillResponse,
    summary="获取 Skill 详情",
    description="根据 ID 获取技能的详细信息。",
    responses={
        200: {"description": "获取成功"},
        404: {"model": SkillErrorResponse, "description": "技能不存在"},
    },
)
async def get_skill(skill_id: int) -> SkillResponse:
    """获取 Skill 详细信息

    Args:
        skill_id: 技能 ID

    Returns:
        SkillResponse: 技能详细信息

    Raises:
        HTTPException: 技能不存在时返回 404
    """
    if skill_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid skill ID",
        )

    skill = _storage.get(skill_id)

    if not skill:
        logger.debug("Skill not found", skill_id=skill_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill with id {skill_id} not found",
        )

    return _build_skill_response(skill)


@router.put(
    "/{skill_id}",
    response_model=SkillResponse,
    summary="更新 Skill",
    description="更新技能信息。支持部分更新。",
    responses={
        200: {"description": "更新成功"},
        400: {"model": SkillErrorResponse, "description": "名称冲突"},
        404: {"model": SkillErrorResponse, "description": "技能不存在"},
    },
)
async def update_skill(
    skill_id: int,
    skill_update: SkillUpdate,
) -> SkillResponse:
    """更新 Skill

    Args:
        skill_id: 技能 ID
        skill_update: 更新数据

    Returns:
        SkillResponse: 更新后的技能信息

    Raises:
        HTTPException: 技能不存在或名称冲突
    """
    skill = _storage.get(skill_id)

    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill with id {skill_id} not found",
        )

    # 获取更新数据
    update_data = skill_update.model_dump(exclude_unset=True)

    if not update_data:
        # 没有更新数据，直接返回当前技能
        return _build_skill_response(skill)

    # 检查名称冲突
    if "name" in update_data and update_data["name"] != skill["name"]:
        existing = _storage.get_by_name(update_data["name"])
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Skill with name '{update_data['name']}' already exists",
            )

    # 更新时间戳
    update_data["updated_at"] = datetime.now()

    # 执行更新
    success = _storage.update(skill_id, update_data)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update skill",
        )

    # 获取更新后的数据
    updated_skill = _storage.get(skill_id)
    logger.info(
        "Skill updated",
        skill_id=skill_id,
        updates=list(update_data.keys()),
    )

    return _build_skill_response(updated_skill)


@router.delete(
    "/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除 Skill",
    description="根据 ID 删除技能。此操作不可逆。",
    responses={
        204: {"description": "删除成功"},
        404: {"model": SkillErrorResponse, "description": "技能不存在"},
    },
)
async def delete_skill(skill_id: int) -> None:
    """删除 Skill

    Args:
        skill_id: 技能 ID

    Returns:
        None

    Raises:
        HTTPException: 技能不存在时返回 404
    """
    success = _storage.delete(skill_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill with id {skill_id} not found",
        )

    logger.info("Skill deleted", skill_id=skill_id)
    return None


@router.patch(
    "/{skill_id}/toggle",
    response_model=SkillResponse,
    summary="切换 Skill 状态",
    description="快速切换技能的启用/禁用状态。",
    responses={
        200: {"description": "切换成功"},
        404: {"model": SkillErrorResponse, "description": "技能不存在"},
    },
)
async def toggle_skill_status(skill_id: int) -> SkillResponse:
    """切换 Skill 启用状态

    Args:
        skill_id: 技能 ID

    Returns:
        SkillResponse: 更新后的技能信息

    Raises:
        HTTPException: 技能不存在时返回 404
    """
    skill = _storage.get(skill_id)

    if not skill:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Skill with id {skill_id} not found",
        )

    new_status = not skill["enabled"]
    _storage.update(skill_id, {
        "enabled": new_status,
        "updated_at": datetime.now(),
    })

    updated_skill = _storage.get(skill_id)
    logger.info(
        "Skill status toggled",
        skill_id=skill_id,
        new_status=new_status,
    )

    return _build_skill_response(updated_skill)
