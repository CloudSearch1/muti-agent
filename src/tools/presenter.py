"""
工具呈现器

职责：
1. 生成系统提示文本（人类可读的工具说明）
2. 生成 API tool schemas（结构化的 JSON Schema）
3. 双通道输出验证一致性

工具暴露协议流程：
1. 接收有效工具集（来自策略引擎）
2. 生成系统提示中的工具说明（可读）
3. 生成 API tool schemas（结构化）
4. 两者取交集，验证一致性
5. 返回双通道输出

使用示例:
    from src.tools.registry import get_registry
    from src.tools.presenter import ToolPresenter

    registry = get_registry()
    presenter = ToolPresenter(registry)

    # 双通道输出
    presentation = presenter.present({"read", "write", "exec"})

    print(presentation.system_prompt)  # 人类可读的工具说明
    print(presentation.api_schemas)    # API tool schemas
"""

from typing import Any

import structlog
from pydantic import BaseModel, Field

from .base import BaseTool, ToolParameter
from .registry import ToolRegistry

logger = structlog.get_logger(__name__)


class ToolPresentation(BaseModel):
    """
    工具呈现结果

    包含双通道输出：系统提示文本和 API schemas
    """

    system_prompt: str = Field(..., description="系统提示文本（人类可读）")
    api_schemas: list[dict[str, Any]] = Field(
        default_factory=list, description="API tool schemas（结构化）"
    )
    tool_count: int = Field(..., description="暴露的工具数量")
    validation_passed: bool = Field(
        default=True, description="一致性验证是否通过"
    )
    warnings: list[str] = Field(default_factory=list, description="警告信息")


class ToolPresenter:
    """
    工具呈现器

    负责：
    - 生成系统提示中的工具说明
    - 生成符合 OpenAI function calling 格式的 API schemas
    - 验证双通道输出一致性
    """

    def __init__(self, registry: ToolRegistry):
        """
        初始化工具呈现器

        Args:
            registry: 工具注册中心实例
        """
        self.registry = registry
        self.logger = logger.bind(component="ToolPresenter")

    def generate_system_prompt(self, tool_names: set[str]) -> str:
        """
        生成系统提示文本

        Args:
            tool_names: 要呈现的工具名称集合

        Returns:
            人类可读的工具说明 Markdown 文本
        """
        if not tool_names:
            return "## Available Tools\n\nNo tools are currently available."

        lines = ["## Available Tools\n", "You have access to the following tools:\n"]

        # 按名称排序，确保输出一致性
        sorted_names = sorted(tool_names)

        for tool_name in sorted_names:
            tool = self.registry.get(tool_name)
            if tool is None:
                self.logger.warning(
                    "Tool not found in registry",
                    tool_name=tool_name,
                )
                continue

            lines.append(self._format_tool_for_prompt(tool))
            lines.append("")  # 空行分隔

        return "\n".join(lines).strip()

    def _format_tool_for_prompt(self, tool: BaseTool) -> str:
        """
        将单个工具格式化为系统提示文本

        Args:
            tool: 工具实例

        Returns:
            Markdown 格式的工具说明
        """
        lines = [f"### {tool.NAME}"]

        # 添加描述
        description = tool.DESCRIPTION or "No description available."
        lines.append(f"\n{description}\n")

        # 获取 action 参数（多动作工具）
        action_param = self._get_action_parameter(tool)

        if action_param:
            # 多动作工具：显示可用动作
            lines.append("**Actions:**")
            for action in action_param.enum or []:
                lines.append(f"- `{action}`")
            lines.append("")

        # 添加参数说明
        params = tool.parameters
        if params:
            lines.append("**Parameters:**")

            # 区分 action 参数和其他参数
            other_params = [p for p in params if p.name != "action"]

            for param in other_params:
                param_line = self._format_parameter_for_prompt(param)
                lines.append(f"- {param_line}")

        return "\n".join(lines)

    def _format_parameter_for_prompt(self, param: ToolParameter) -> str:
        """
        将参数格式化为系统提示文本

        Args:
            param: 参数定义

        Returns:
            参数说明字符串
        """
        parts = [f"**{param.name}**"]

        # 类型信息
        type_info = f"({param.type}"
        if param.required:
            type_info += ", required"
        else:
            type_info += ", optional"
        type_info += ")"
        parts.append(type_info)

        # 描述
        parts.append(f": {param.description}")

        # 默认值
        if param.default is not None:
            parts.append(f", default `{param.default}`")

        # 枚举值
        if param.enum:
            enum_values = ", ".join(f"`{v}`" for v in param.enum)
            parts.append(f". One of: {enum_values}")

        return " ".join(parts)

    def _get_action_parameter(self, tool: BaseTool) -> ToolParameter | None:
        """
        获取工具的 action 参数（如果存在）

        Args:
            tool: 工具实例

        Returns:
            action 参数定义，不存在则返回 None
        """
        for param in tool.parameters:
            if param.name == "action" and param.enum:
                return param
        return None

    def generate_api_schemas(self, tool_names: set[str]) -> list[dict[str, Any]]:
        """
        生成 API tool schemas

        符合 OpenAI function calling 格式，包含：
        - name: 工具名称
        - description: 工具描述
        - parameters: JSON Schema 格式的参数定义

        Args:
            tool_names: 要呈现的工具名称集合

        Returns:
            API tool schemas 列表
        """
        schemas = []

        # 按名称排序，确保输出一致性
        sorted_names = sorted(tool_names)

        for tool_name in sorted_names:
            tool = self.registry.get(tool_name)
            if tool is None:
                self.logger.warning(
                    "Tool not found in registry",
                    tool_name=tool_name,
                )
                continue

            schema = self._generate_tool_schema(tool)
            schemas.append(schema)

        return schemas

    def _generate_tool_schema(self, tool: BaseTool) -> dict[str, Any]:
        """
        为单个工具生成 API schema

        Args:
            tool: 工具实例

        Returns:
            OpenAI function calling 格式的 schema
        """
        parameters_schema = self._generate_parameters_schema(tool)

        schema: dict[str, Any] = {
            "type": "function",
            "function": {
                "name": tool.NAME,
                "description": tool.DESCRIPTION or "No description available.",
                "parameters": parameters_schema,
            },
            "x-schema-version": tool.SCHEMA_VERSION,
        }

        # 添加输出模式定义（如果工具定义了 output_schema）
        if tool.output_schema:
            schema["x-output-schema"] = tool.output_schema.to_dict()

        return schema

    def _generate_parameters_schema(self, tool: BaseTool) -> dict[str, Any]:
        """
        生成参数的 JSON Schema

        Args:
            tool: 工具实例

        Returns:
            JSON Schema 格式的参数定义
        """
        properties: dict[str, Any] = {}
        required: list[str] = []

        for param in tool.parameters:
            # 生成属性定义
            prop_schema = self._parameter_to_json_schema(param)
            properties[param.name] = prop_schema

            # 记录必填参数
            if param.required:
                required.append(param.name)

        schema: dict[str, Any] = {
            "type": "object",
            "properties": properties,
        }

        if required:
            schema["required"] = required

        return schema

    def _parameter_to_json_schema(self, param: ToolParameter) -> dict[str, Any]:
        """
        将 ToolParameter 转换为 JSON Schema

        Args:
            param: 参数定义

        Returns:
            JSON Schema 格式的参数定义
        """
        # 类型映射
        type_mapping = {
            "string": "string",
            "integer": "integer",
            "number": "number",
            "boolean": "boolean",
            "array": "array",
            "object": "object",
        }

        json_type = type_mapping.get(param.type, "string")

        schema: dict[str, Any] = {
            "type": json_type,
            "description": param.description,
        }

        # 枚举值
        if param.enum:
            schema["enum"] = param.enum

        # 默认值
        if param.default is not None:
            schema["default"] = param.default

        # 数组类型需要 items
        if json_type == "array":
            schema["items"] = {"type": "string"}

        return schema

    def present(self, tool_names: set[str]) -> ToolPresentation:
        """
        双通道输出

        生成系统提示文本和 API schemas，并验证一致性

        Args:
            tool_names: 要呈现的工具名称集合

        Returns:
            ToolPresentation 包含双通道输出
        """
        warnings: list[str] = []

        # 过滤出实际存在的工具
        valid_tools: set[str] = set()
        missing_tools: set[str] = set()

        for tool_name in tool_names:
            if self.registry.has_tool(tool_name):
                valid_tools.add(tool_name)
            else:
                missing_tools.add(tool_name)
                warnings.append(f"Tool not found in registry: {tool_name}")

        if missing_tools:
            self.logger.warning(
                "Some tools not found in registry",
                missing_tools=list(missing_tools),
            )

        # 生成双通道输出
        system_prompt = self.generate_system_prompt(valid_tools)
        api_schemas = self.generate_api_schemas(valid_tools)

        # 一致性验证
        prompt_tools = self._extract_tools_from_prompt(system_prompt)
        schema_tools = {schema["function"]["name"] for schema in api_schemas}

        validation_passed = True

        # 检查系统提示中的工具是否都在 schemas 中
        tools_only_in_prompt = prompt_tools - schema_tools
        if tools_only_in_prompt:
            validation_passed = False
            warnings.append(
                f"Tools in system prompt but not in API schemas: {tools_only_in_prompt}"
            )

        # 检查 schemas 中的工具是否都在系统提示中
        tools_only_in_schema = schema_tools - prompt_tools
        if tools_only_in_schema:
            validation_passed = False
            warnings.append(
                f"Tools in API schemas but not in system prompt: {tools_only_in_schema}"
            )

        # 检查工具数量一致性
        if len(prompt_tools) != len(schema_tools):
            validation_passed = False
            warnings.append(
                f"Tool count mismatch: prompt has {len(prompt_tools)}, "
                f"schemas have {len(schema_tools)}"
            )

        if warnings:
            self.logger.warning(
                "Validation warnings during tool presentation",
                warnings=warnings,
            )

        return ToolPresentation(
            system_prompt=system_prompt,
            api_schemas=api_schemas,
            tool_count=len(valid_tools),
            validation_passed=validation_passed,
            warnings=warnings,
        )

    def _extract_tools_from_prompt(self, prompt: str) -> set[str]:
        """
        从系统提示中提取工具名称

        Args:
            prompt: 系统提示文本

        Returns:
            提取的工具名称集合
        """
        tools: set[str] = set()

        # 解析 "### tool_name" 格式
        lines = prompt.split("\n")
        for line in lines:
            if line.startswith("### "):
                tool_name = line[4:].strip()
                if tool_name:
                    tools.add(tool_name)

        return tools

    def generate_tool_description(
        self, tool_name: str, include_examples: bool = False
    ) -> str:
        """
        生成单个工具的详细描述

        Args:
            tool_name: 工具名称
            include_examples: 是否包含使用示例

        Returns:
            工具的详细描述文本
        """
        tool = self.registry.get(tool_name)
        if tool is None:
            return f"Tool '{tool_name}' not found."

        lines = [f"# {tool.NAME}", "", tool.DESCRIPTION or "No description.", ""]

        # 参数详情
        params = tool.parameters
        if params:
            lines.append("## Parameters")
            lines.append("")
            lines.append("| Name | Type | Required | Description |")
            lines.append("|------|------|----------|-------------|")

            for param in params:
                required = "Yes" if param.required else "No"
                lines.append(
                    f"| {param.name} | {param.type} | {required} | {param.description} |"
                )

        if include_examples:
            lines.append("")
            lines.append("## Example Usage")
            lines.append("")
            lines.append("```python")
            lines.append(f"result = await registry.execute('{tool.NAME}', ")
            # 构造示例参数
            example_params = []
            for param in params:
                if param.required:
                    if param.enum:
                        example_params.append(f"    {param.name}='{param.enum[0]}'")
                    elif param.type == "string":
                        example_params.append(f"    {param.name}='example'")
                    elif param.type == "integer":
                        example_params.append(f"    {param.name}=1")
                    elif param.type == "boolean":
                        example_params.append(f"    {param.name}=True")

            lines.append(",\n".join(example_params) if example_params else "    **kwargs")
            lines.append(")")
            lines.append("```")

        return "\n".join(lines)


# 便捷函数
def present_tools(tool_names: set[str]) -> ToolPresentation:
    """
    便捷函数：双通道输出工具

    Args:
        tool_names: 要呈现的工具名称集合

    Returns:
        ToolPresentation 包含双通道输出
    """
    from .registry import get_registry

    presenter = ToolPresenter(get_registry())
    return presenter.present(tool_names)


def generate_system_prompt(tool_names: set[str]) -> str:
    """
    便捷函数：生成系统提示文本

    Args:
        tool_names: 要呈现的工具名称集合

    Returns:
        人类可读的工具说明
    """
    from .registry import get_registry

    presenter = ToolPresenter(get_registry())
    return presenter.generate_system_prompt(tool_names)


def generate_api_schemas(tool_names: set[str]) -> list[dict[str, Any]]:
    """
    便捷函数：生成 API tool schemas

    Args:
        tool_names: 要呈现的工具名称集合

    Returns:
        API tool schemas 列表
    """
    from .registry import get_registry

    presenter = ToolPresenter(get_registry())
    return presenter.generate_api_schemas(tool_names)
