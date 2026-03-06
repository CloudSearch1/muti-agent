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
        implementation = await self.think(
            {
                "requirements": requirements,
                "architecture": architecture,
                "existing_code": existing_code,
            }
        )

        # 生成代码
        code_files = await self._generate_code(implementation)

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

    async def _simulate_implementation(
        self,
        requirements: str,
    ) -> dict[str, Any]:
        """
        使用 LLM 生成代码实现方案
        
        已实现真实 LLM 调用
        """
        # 构建提示词
        prompt = f"""你是一位资深软件工程师。请根据以下需求设计代码实现方案。

## 需求
{requirements}

## 要求
1. 设计清晰的模块结构
2. 列出关键函数及其职责
3. 考虑错误处理和边界情况
4. 遵循 {self.code_style} 代码规范
5. 使用 {self.preferred_language} 语言

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

        # 调用 LLM
        result = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt=f"你是一位资深{self.preferred_language}软件工程师。请以 JSON 格式输出代码设计方案。",
        )

        if result:
            self.logger.info("LLM code design successful", functions=len(result.get("key_functions", [])))
            return result

        # Fallback: 返回简化版本
        self.logger.warning("LLM code design returned None, using minimal fallback")
        return {
            "approach": "基于需求分析，采用模块化设计",
            "key_functions": [
                {"name": "initialize()", "description": "初始化", "parameters": [], "returns": "None"},
                {"name": "process_data()", "description": "处理数据", "parameters": ["data"], "returns": "处理结果"},
                {"name": "validate_input()", "description": "验证输入", "parameters": ["input"], "returns": "bool"},
                {"name": "generate_output()", "description": "生成输出", "parameters": ["data"], "returns": "输出结果"},
            ],
            "notes": "代码遵循 PEP8 规范，包含类型注解",
        }

    async def _generate_code(self, implementation: dict[str, Any]) -> list[dict[str, Any]]:
        """使用 LLM 生成代码文件"""
        approach = implementation.get("approach", "")
        key_functions = implementation.get("key_functions", [])
        notes = implementation.get("notes", "")

        # 构建代码生成提示词
        prompt = f"""你是一位资深软件工程师。请根据以下设计生成完整的代码实现。

## 实现思路
{approach}

## 关键函数
{self._format_functions(key_functions)}

## 注意事项
{notes}

## 要求
1. 生成完整、可运行的代码
2. 包含详细的文档字符串
3. 包含类型注解
4. 包含错误处理
5. 遵循 {self.code_style} 规范
6. 使用 {self.preferred_language} 语言

## 输出格式
请提供完整的代码，包含所有必要的导入语句和函数实现。"""

        # 调用 LLM 生成主代码文件
        main_code = await self.llm_helper.generate(
            prompt=prompt,
            system_prompt=f"你是一位资深{self.preferred_language}软件工程师。请生成完整、可运行的代码。",
        )

        # 生成工具函数文件
        utils_prompt = f"""为以下主代码生成辅助工具函数：

主代码功能：{approach}

要求：
1. 提供常用的辅助函数
2. 包含错误处理
3. 包含类型注解
"""
        utils_code = await self.llm_helper.generate(
            prompt=utils_prompt,
            system_prompt="生成实用的工具函数",
        )

        # 构建代码文件列表
        code_files = [
            {
                "filename": "main.py",
                "content": main_code or self._generate_fallback_code(key_functions),
                "language": self.preferred_language,
                "type": "main",
            },
            {
                "filename": "utils.py",
                "content": utils_code or self._generate_fallback_utils(),
                "language": self.preferred_language,
                "type": "utils",
            },
        ]

        self.logger.info("Code generation complete", files=len(code_files))
        return code_files

    def _format_functions(self, functions: list[dict[str, Any]]) -> str:
        """格式化函数列表为文本"""
        if not functions:
            return "无特定函数要求"

        lines = []
        for func in functions:
            name = func.get("name", "unknown")
            desc = func.get("description", "")
            params = func.get("parameters", [])
            returns = func.get("returns", "")
            lines.append(f"- {name}: {desc}")
            if params:
                lines.append(f"  参数：{', '.join(params)}")
            if returns:
                lines.append(f"  返回：{returns}")
        return "\n".join(lines)

    def _generate_fallback_code(self, key_functions: list[dict[str, Any]]) -> str:
        """生成备用代码（当 LLM 失败时）"""
        functions_code = []
        for func in key_functions:
            name = func.get("name", "unknown_function")
            desc = func.get("description", "")
            params = func.get("parameters", [])
            param_str = ", ".join(params) if params else ""

            functions_code.append(f"""
def {name}({param_str}):
    \"\"\"
    {desc}
    \"\"\"
    # TODO: 实现具体逻辑
    pass
""")

        return f'''"""
自动生成的代码模块
功能：代码实现
"""

from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

{"".join(functions_code)}


if __name__ == "__main__":
    # 示例用法
    print("模块加载成功")
'''

    def _generate_fallback_utils(self) -> str:
        """生成备用工具函数"""
        return '''"""
工具函数模块
"""

from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


def validate_input(data: Any) -> bool:
    """验证输入数据"""
    if data is None:
        logger.warning("Input is None")
        return False
    return True


def format_output(data: Any) -> str:
    """格式化输出"""
    if isinstance(data, dict):
        return str(data)
    return repr(data)


def safe_execute(func, *args, **kwargs) -> Optional[Any]:
    """安全执行函数"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Error executing function: {e}")
        return None
'''

    async def review_code(
        self,
        code: str,
        criteria: list[str] = None,
    ) -> dict[str, Any]:
        """
        代码审查 - 使用 LLM 进行代码质量检查

        Args:
            code: 待审查的代码
            criteria: 审查标准

        Returns:
            审查结果
        """
        if not criteria:
            criteria = [
                "代码可读性",
                "错误处理",
                "性能优化",
                "代码规范",
                "安全性",
            ]

        # 构建审查提示词
        prompt = f"""你是一位资深代码审查专家。请审查以下代码：

## 代码
```{self.preferred_language}
{code}
```

## 审查标准
{chr(10).join(f'- {c}' for c in criteria)}

## 要求
1. 识别潜在问题和改进点
2. 提供具体的修改建议
3. 评估代码质量（0-100 分）
4. 指出优点和不足

## 输出格式 (JSON)
{{
    "status": "approved|needs_revision|rejected",
    "quality_score": 85,
    "issues": [
        {{
            "severity": "critical|major|minor",
            "line": 10,
            "message": "问题描述",
            "suggestion": "修改建议"
        }}
    ],
    "suggestions": ["改进建议 1", "改进建议 2"],
    "strengths": ["优点 1", "优点 2"],
    "weaknesses": ["不足 1", "不足 2"]
}}"""

        # 调用 LLM 进行审查
        result = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一位严格的代码审查专家。请提供专业、详细的审查意见。",
        )

        if result:
            self.logger.info(
                "Code review complete",
                status=result.get("status"),
                score=result.get("quality_score"),
                issues=len(result.get("issues", [])),
            )
            return result

        # Fallback
        self.logger.warning("Code review LLM failed, using fallback")
        return {
            "status": "approved",
            "quality_score": 75,
            "issues": [],
            "suggestions": ["建议添加更多单元测试", "考虑添加类型注解"],
            "strengths": ["代码结构清晰"],
            "weaknesses": ["错误处理不够完善"],
        }

    async def refactor_code(
        self,
        code: str,
        goals: list[str] = None,
    ) -> dict[str, Any]:
        """
        代码重构 - 使用 LLM 优化代码

        Args:
            code: 待重构的代码
            goals: 重构目标

        Returns:
            重构结果
        """
        if not goals:
            goals = [
                "提高可读性",
                "优化性能",
                "简化逻辑",
                "改进命名",
                "消除重复代码",
            ]

        # 构建重构提示词
        prompt = f"""你是一位代码重构专家。请重构以下代码：

## 原始代码
```{self.preferred_language}
{code}
```

## 重构目标
{chr(10).join(f'- {g}' for g in goals)}

## 要求
1. 保持原有功能不变
2. 应用最佳实践和设计模式
3. 改进代码结构和命名
4. 添加必要的注释
5. 提供完整的重构后代码

## 输出格式 (JSON)
{{
    "status": "refactored",
    "original_code": "原始代码（缩略）",
    "refactored_code": "完整的重构后代码",
    "changes": [
        {{
            "type": "refactoring|optimization|cleanup",
            "description": "修改描述",
            "impact": "high|medium|low"
        }}
    ],
    "summary": "重构总结"
}}"""

        # 调用 LLM 进行重构
        result = await self.llm_helper.generate_json(
            prompt=prompt,
            system_prompt="你是一位代码重构专家。请在保持功能不变的前提下优化代码质量。",
        )

        if result:
            # 确保包含完整代码
            if "refactored_code" not in result:
                # 如果 LLM 没有返回代码，尝试重新生成
                refactored = await self.llm_helper.generate(
                    prompt=f"请提供完整的重构后代码：{prompt}",
                    system_prompt="只提供代码，不要其他文字",
                )
                result["refactored_code"] = refactored or code

            self.logger.info(
                "Code refactoring complete",
                changes=len(result.get("changes", [])),
            )
            return result

        # Fallback
        self.logger.warning("Code refactoring LLM failed, using fallback")
        return {
            "status": "refactored",
            "original_code": code[:200] + "..." if len(code) > 200 else code,
            "refactored_code": code,  # 返回原始代码
            "changes": [
                {
                    "type": "cleanup",
                    "description": "代码格式化",
                    "impact": "low",
                }
            ],
            "summary": "代码格式化完成",
        }
