"""
CoderAgent - 代码工程师 Agent

职责：代码编写、重构、代码审查
"""

from typing import Any

import structlog

from ..core.models import AgentRole, Task
from .base import BaseAgent
from .llm_helper import get_coder_llm

logger = structlog.get_logger(__name__)


class CoderAgent(BaseAgent):
    """
    代码工程师
    
    负责：
    - 根据设计文档编写代码
    - 代码重构和优化
    - 代码审查
    - 技术债务管理
    """

    ROLE = AgentRole.CODER

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # 程序员特有配置
        self.coding_model = kwargs.get("coding_model", "gpt-4")
        self.preferred_language = kwargs.get("preferred_language", "python")
        self.code_style = kwargs.get("code_style", "pep8")
        
        # LLM 辅助
        self.llm_helper = get_coder_llm()

        self.logger.info("CoderAgent initialized")

    async def execute(self, task: Task) -> dict[str, Any]:
        """
        执行编码任务
        """
        self.logger.info(
            "Starting coding task",
            task_id=task.id,
            task_title=task.title,
        )

        # 获取任务输入
        requirements = task.input_data.get("requirements", "")
        architecture = task.input_data.get("architecture", {})
        existing_code = task.input_data.get("existing_code", None)

        # 思考实现方案
        implementation = await self.think({
            "requirements": requirements,
            "architecture": architecture,
            "existing_code": existing_code,
        })

        # 生成代码
        code_files = self._generate_code(implementation)

        # 存储到黑板
        self.put_to_blackboard(
            f"code:{task.id}",
            code_files,
            description="生成的代码文件",
        )

        return {
            "status": "coding_complete",
            "files_created": len(code_files),
            "code_files": code_files,
            "implementation_notes": implementation.get("notes", ""),
        }

    async def think(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        思考代码实现方案
        """
        requirements = context.get("requirements", "")
        architecture = context.get("architecture", {})

        # 尝试使用 LLM 进行代码设计
        if self.llm_helper.is_available():
            try:
                result = await self._llm_design(requirements, architecture)
                if result:
                    return result
            except Exception as e:
                self.logger.warning("LLM code design failed, using fallback", error=str(e))

        # Fallback: 使用模拟实现
        return self._simulate_implementation(requirements)
    
    async def _llm_design(
        self,
        requirements: str,
        architecture: dict[str, Any],
    ) -> dict[str, Any] | None:
        """使用 LLM 设计代码实现方案"""
        prompt = f"""你是一位资深软件工程师。请根据以下需求设计代码实现方案。

## 需求
{requirements}

## 架构设计
{architecture if architecture else "无特定架构要求"}

## 要求
1. 设计清晰的模块结构
2. 列出关键函数及其职责
3. 考虑错误处理和边界情况
4. 遵循 {self.code_style} 代码规范

## 输出格式 (JSON)
{{
    "approach": "实现思路说明",
    "key_functions": [
        {{
            "name": "函数名",
            "description": "功能描述",
            "parameters": ["参数列表"],
            "returns": "返回值说明"
        }}
    ],
    "notes": "实现注意事项"
}}"""

        result = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt=f"你是一位资深{self.preferred_language}软件工程师。请以 JSON 格式输出代码设计方案。",
        )
        
        if result:
            return result
        
        return None

    def _build_coding_prompt(
        self,
        requirements: str,
        architecture: dict[str, Any],
    ) -> str:
        """构建编码提示词"""
        return f"""
你是一位资深软件工程师。请根据以下需求和架构设计编写代码。

## 需求
{requirements}

## 架构设计
{architecture}

## 要求
1. 遵循最佳实践和设计模式
2. 代码简洁、可读性强
3. 包含必要的注释和文档字符串
4. 考虑错误处理和边界情况
5. 编写单元测试

## 输出格式
提供完整的代码实现
"""

    def _simulate_implementation(
        self,
        requirements: str,
    ) -> dict[str, Any]:
        """
        模拟代码实现结果 (临时实现)
        
        TODO: 替换为真实 LLM 调用
        """
        return {
            "approach": "基于需求分析，采用模块化设计",
            "key_functions": [
                "initialize()",
                "process_data()",
                "validate_input()",
                "generate_output()",
            ],
            "notes": "代码遵循 PEP8 规范，包含类型注解",
        }

    def _generate_code(self, implementation: dict[str, Any]) -> list[dict[str, Any]]:
        """生成代码文件"""
        # TODO: 生成真实代码
        return [
            {
                "filename": "main.py",
                "content": "# TODO: 生成实际代码\n\ndef main():\n    pass\n",
                "language": "python",
            },
            {
                "filename": "utils.py",
                "content": "# TODO: 生成工具函数\n\ndef helper():\n    pass\n",
                "language": "python",
            },
        ]

    async def review_code(
        self,
        code: str,
        criteria: list[str] = None,
    ) -> dict[str, Any]:
        """
        代码审查
        
        Args:
            code: 待审查的代码
            criteria: 审查标准
            
        Returns:
            审查结果
        """
        # TODO: 实现代码审查逻辑
        return {
            "status": "approved",
            "issues": [],
            "suggestions": [],
            "quality_score": 85,
        }

    async def refactor_code(
        self,
        code: str,
        goals: list[str] = None,
    ) -> dict[str, Any]:
        """
        代码重构
        
        Args:
            code: 待重构的代码
            goals: 重构目标
            
        Returns:
            重构结果
        """
        # TODO: 实现代码重构逻辑
        return {
            "status": "refactored",
            "original_code": code,
            "refactored_code": "# TODO: 重构后的代码",
            "changes": [],
        }
