"""
工具适配器

将 IntelliTeam 工具适配为 LangChain 工具格式。
"""

import asyncio
import functools
from typing import Any, Callable, Optional, Dict, List, Type

from pydantic import BaseModel, create_model, Field

# 修复 LangChain 新版本的导入路径
try:
    from langchain_core.tools import BaseTool as LangChainTool
    from langchain_core.tools import StructuredTool
except ImportError:
    from langchain.tools import BaseTool as LangChainTool
    from langchain.tools import StructuredTool

import structlog

logger = structlog.get_logger(__name__)


def _create_args_schema_from_parameters(tool: Any) -> Optional[Type[BaseModel]]:
    """
    从工具的 parameters 属性创建 Pydantic 模型作为 args_schema
    
    注意：所有字段都设置为可选，因为：
    1. LLM 可能输出嵌套 JSON 格式
    2. 实际的参数解析在包装函数中完成
    3. 避免验证失败导致工具无法执行
    
    Args:
        tool: 具有 parameters 属性的工具实例
        
    Returns:
        Pydantic 模型类，或 None
    """
    parameters = getattr(tool, "parameters", None)
    if not parameters:
        return None
    
    # 构建 Pydantic 模型字段
    fields: Dict[str, tuple] = {}
    
    for param in parameters:
        param_name = param.name
        param_type = param.type
        param_description = param.description
        param_default = param.default
        
        # 类型映射
        type_mapping = {
            "string": str,
            "integer": int,
            "float": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        
        python_type = type_mapping.get(param_type, str)
        
        # 所有字段都设为可选，避免验证失败
        # 实际的必填检查在工具内部进行
        fields[param_name] = (
            Optional[python_type],
            Field(default=param_default, description=param_description)
        )
    
    if not fields:
        return None
    
    # 动态创建 Pydantic 模型
    tool_name = getattr(tool, "NAME", tool.__class__.__name__)
    schema_name = f"{tool_name}Args"
    
    try:
        # 创建模型，允许额外字段
        model = create_model(
            schema_name,
            __base__=BaseModel,
            **fields
        )
        # 设置允许额外字段
        model.model_config = {"extra": "allow"}
        return model
    except Exception as e:
        logger.warning(f"Failed to create args schema: {e}")
        return None


def _create_flexible_args_schema(tool_name: str) -> Type[BaseModel]:
    """
    创建一个灵活的 args_schema，接受任意输入
    
    这个 schema 允许任意字段，避免 Pydantic 验证失败。
    实际的参数解析在包装函数中完成。
    
    Args:
        tool_name: 工具名称
        
    Returns:
        接受任意字段的 Pydantic 模型类
    """
    # 检测 Pydantic 版本
    import pydantic
    pydantic_version = int(pydantic.__version__.split('.')[0])
    
    if pydantic_version >= 2:
        # Pydantic v2: 使用 model_config 和 __pydantic_extra__
        class FlexibleArgsBase(BaseModel):
            """灵活的参数模型基类 - Pydantic v2"""
            model_config = {"extra": "allow"}
            
            def model_post_init(self, __context):
                # 确保额外字段被保留
                pass
    else:
        # Pydantic v1: 使用 Config.extra = "allow"
        class FlexibleArgsBase(BaseModel):
            """灵活的参数模型基类 - Pydantic v1"""
            class Config:
                extra = "allow"
    
    # 重命名模型类
    FlexibleArgsBase.__name__ = f"{tool_name}Args"
    FlexibleArgsBase.__qualname__ = f"{tool_name}Args"
    
    return FlexibleArgsBase


class ToolAdapter:
    """
    工具适配器
    
    将 IntelliTeam 的工具转换为 LangChain 工具格式，
    使其可以在 ReAct Agent 中使用。
    """
    
    @staticmethod
    def _parse_tool_input(tool_input: Any) -> dict:
        """
        解析工具输入，处理多种输入格式
        
        LangChain ReAct 可能传递以下格式的输入：
        1. 字符串（需要解析）
        2. 字典（直接使用）
        3. JSON 字符串（需要解析）
        
        Args:
            tool_input: 工具输入
            
        Returns:
            解析后的参数字典
        """
        import json
        
        if isinstance(tool_input, dict):
            # 已经是字典，检查是否需要提取嵌套的 JSON
            # 处理 {'action': '{"action": "list", "path": "."}'} 这种情况
            result = {}
            for key, value in tool_input.items():
                if isinstance(value, str) and value.strip().startswith('{'):
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, dict):
                            result.update(parsed)
                            continue
                    except json.JSONDecodeError:
                        pass
                result[key] = value
            return result
        
        if isinstance(tool_input, str):
            # 尝试解析 JSON 字符串
            tool_input = tool_input.strip()
            if tool_input.startswith('{'):
                try:
                    return json.loads(tool_input)
                except json.JSONDecodeError:
                    pass
            
            # 尝试解析 "action path" 格式（空格分隔）
            parts = tool_input.split(None, 1)
            if len(parts) >= 1:
                result = {"action": parts[0]}
                if len(parts) >= 2:
                    result["path"] = parts[1]
                return result
            
            return {"input": tool_input}
        
        # 其他类型，包装为字典
        return {"input": tool_input}
    
    @staticmethod
    def _is_async_callable(func: Callable) -> bool:
        """
        检测函数是否是异步的
        
        Args:
            func: 要检测的函数
            
        Returns:
            是否是异步函数
        """
        import asyncio
        import inspect
        
        # 检查是否是协程函数
        if asyncio.iscoroutinefunction(func):
            return True
        
        # 检查是否是异步方法
        if inspect.iscoroutinefunction(func):
            return True
        
        # 检查是否是绑定方法且原函数是异步的
        if hasattr(func, '__func__'):
            if asyncio.iscoroutinefunction(func.__func__):
                return True
        
        return False
    
    @staticmethod
    def _wrap_input_parser(func: Callable, tool_instance: Any = None) -> Callable:
        """
        包装函数，在执行前解析输入
        
        注意：此方法仅用于同步函数。如果是异步函数，请使用 _wrap_async_input_parser。
        
        Args:
            func: 原始执行函数
            tool_instance: 工具实例
            
        Returns:
            包装后的函数
        """
        import functools
        
        # 检测是否是异步函数，如果是则返回 None 表示需要使用异步包装器
        if ToolAdapter._is_async_callable(func):
            logger.debug(f"Function {func} is async, should use _wrap_async_input_parser instead")
            return None  # 返回 None 表示调用者应该使用异步包装器
        
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            # 如果第一个参数是字典或字符串，尝试解析
            if args and len(args) == 1:
                parsed = ToolAdapter._parse_tool_input(args[0])
                return func(**parsed)
            return func(*args, **kwargs)
        
        return wrapped
    
    @staticmethod
    def adapt(
        tool: Any,
        name: Optional[str] = None,
        description: Optional[str] = None,
        args_schema: Optional[Any] = None,
    ) -> LangChainTool:
        """
        将 IntelliTeam 工具适配为 LangChain 工具
        
        Args:
            tool: IntelliTeam 工具实例
            name: 工具名称（可选，默认使用 tool.NAME）
            description: 工具描述（可选，默认使用 tool.DESCRIPTION）
            args_schema: 参数 Schema（可选，默认自动从 tool.parameters 生成）
        
        Returns:
            LangChain 工具实例
        
        Example:
            >>> from src.tools import CodeTools
            >>> intelliteam_tool = CodeTools()
            >>> langchain_tool = ToolAdapter.adapt(intelliteam_tool)
        """
        # 获取工具名称
        tool_name = name or getattr(tool, "NAME", None) or getattr(tool, "name", tool.__class__.__name__)
        
        # 获取或构建工具描述
        # 如果没有提供描述，尝试从工具的 parameters 中构建详细描述
        if description:
            tool_description = description
        else:
            base_description = getattr(tool, "DESCRIPTION", None) or getattr(tool, "description", "")
            
            # 从 parameters 构建详细的使用说明
            parameters = getattr(tool, "parameters", None)
            if parameters:
                param_docs = []
                
                # 找到 action 参数（如果存在）
                action_param = None
                for p in parameters:
                    if p.name == "action":
                        action_param = p
                        break
                
                # 构建描述
                if action_param and action_param.enum:
                    # 列出所有可用动作
                    param_docs.append(f"Available actions: {', '.join(action_param.enum)}")
                
                # 添加参数说明
                param_docs.append("Parameters:")
                for p in parameters:
                    if p.name == "action" and p.enum:
                        param_docs.append(f"  - {p.name}: {p.description} (one of: {', '.join(p.enum)})")
                    else:
                        required_mark = " (required)" if p.required else " (optional)"
                        default_info = f", default: {p.default}" if p.default is not None else ""
                        param_docs.append(f"  - {p.name}: {p.description}{required_mark}{default_info}")
                
                tool_description = f"{base_description}\n\n{chr(10).join(param_docs)}"
            else:
                tool_description = base_description or f"Tool: {tool_name}"
        
        # 获取或创建参数 Schema
        # 重要：LangChain 的 ainvoke 方法会使用 args_schema 验证输入，
        # 然后将验证后的字段作为 kwargs 传递给 coroutine。
        # 如果 schema 没有定义字段，参数会丢失！
        if args_schema is None:
            # 尝试从工具的 parameters 属性创建 schema
            parameters = getattr(tool, "parameters", None)
            if parameters:
                args_schema = _create_args_schema_from_parameters(tool)
            
            # 如果创建失败，使用灵活 schema（但可能导致参数丢失）
            if args_schema is None:
                args_schema = _create_flexible_args_schema(tool_name)
                logger.warning(
                    f"Tool {tool_name} has no parameters defined, using flexible schema. "
                    "This may cause parameter loss in LangChain ainvoke."
                )
        
        # 获取执行函数
        sync_func = getattr(tool, "execute", None)
        async_func = getattr(tool, "async_execute", None) or getattr(
            tool, "arun", None
        )
        
        # 如果工具是可调用的（有 __call__ 方法），使用它
        if sync_func is None and callable(tool):
            sync_func = tool.__call__
        
        # 检测 execute 是否是异步方法
        execute_is_async = ToolAdapter._is_async_callable(sync_func)
        
        if execute_is_async:
            # 如果 execute 是异步的，将其作为 async_func
            async_func = sync_func
            sync_func = None
            logger.debug(f"Tool {tool_name} has async execute method")
        
        # 包装同步函数，添加输入解析
        if sync_func:
            wrapped_sync = ToolAdapter._wrap_input_parser(sync_func, tool)
            if wrapped_sync:
                sync_func = wrapped_sync
        
        # 如果没有异步函数，尝试包装同步函数
        if async_func is None and sync_func:
            async_func = ToolAdapter._wrap_sync_to_async(sync_func, tool)
        elif async_func:
            # 包装异步函数，添加输入解析
            async_func = ToolAdapter._wrap_async_input_parser(async_func, tool)
        
        # 创建 LangChain 工具
        return StructuredTool(
            name=tool_name,
            description=tool_description,
            func=sync_func,
            coroutine=async_func,
            args_schema=args_schema,
        )
    
    @staticmethod
    def _wrap_async_input_parser(async_func: Callable, tool_instance: Any = None) -> Callable:
        """
        包装异步函数，在执行前解析输入
        
        Args:
            async_func: 原始异步执行函数
            tool_instance: 工具实例
            
        Returns:
            包装后的异步函数
        """
        import functools
        import json
        
        @functools.wraps(async_func)
        async def wrapped(*args, **kwargs):
            # 调试日志
            logger.debug(
                "wrapped async called",
                args_count=len(args),
                kwargs_keys=list(kwargs.keys()),
            )
            
            # 情况 1: 通过位置参数传递（直接调用 coroutine）
            if args and len(args) == 1:
                parsed = ToolAdapter._parse_tool_input(args[0])
                logger.debug("Parsed from args", parsed=parsed)
                return await async_func(**parsed)
            
            # 情况 2: 通过 kwargs 传递（LangChain ainvoke）
            if kwargs:
                # 检查是否有字段值是 JSON 字符串（嵌套 JSON）
                # 先收集所有解析出的嵌套 JSON
                nested_jsons = []
                for key, value in kwargs.items():
                    if isinstance(value, str) and value.strip().startswith('{'):
                        try:
                            inner = json.loads(value)
                            if isinstance(inner, dict):
                                nested_jsons.append(inner)
                                logger.debug(f"Found nested JSON in key '{key}'", inner=inner)
                        except json.JSONDecodeError:
                            pass
                
                # 如果发现了嵌套 JSON，合并它们（后面的覆盖前面的）
                if nested_jsons:
                    parsed_kwargs = {}
                    for nested in nested_jsons:
                        parsed_kwargs.update(nested)
                    
                    # 过滤掉 kwargs 中的 None 值（它们是 schema 默认填充的）
                    # 但保留非 None 的值
                    for key, value in kwargs.items():
                        if value is not None and key not in parsed_kwargs:
                            parsed_kwargs[key] = value
                    
                    logger.debug("Using parsed kwargs from nested JSON", parsed=parsed_kwargs)
                    return await async_func(**parsed_kwargs)
                
                return await async_func(*args, **kwargs)
            
            return await async_func(*args, **kwargs)
        
        return wrapped
    
    @staticmethod
    def adapt_batch(
        tools: list[Any],
        name_map: Optional[dict[str, str]] = None,
        description_map: Optional[dict[str, str]] = None,
    ) -> list[LangChainTool]:
        """
        批量适配工具
        
        Args:
            tools: IntelliTeam 工具列表
            name_map: 工具名称映射（可选）
            description_map: 工具描述映射（可选）
        
        Returns:
            LangChain 工具列表
        
        Example:
            >>> tools = [CodeTools(), FileTools()]
            >>> langchain_tools = ToolAdapter.adapt_batch(tools)
        """
        name_map = name_map or {}
        description_map = description_map or {}
        
        adapted_tools = []
        for tool in tools:
            tool_name = getattr(tool, "NAME", None) or getattr(tool, "name", tool.__class__.__name__)
            
            adapted_tool = ToolAdapter.adapt(
                tool=tool,
                name=name_map.get(tool_name),
                description=description_map.get(tool_name),
            )
            adapted_tools.append(adapted_tool)
        
        logger.info(
            "Tools adapted",
            count=len(adapted_tools),
            tools=[t.name for t in adapted_tools],
        )
        
        return adapted_tools
    
    @staticmethod
    def adapt_from_function(
        func: Callable,
        name: Optional[str] = None,
        description: str = "",
        args_schema: Optional[Any] = None,
        coroutine: Optional[Callable] = None,
    ) -> LangChainTool:
        """
        从 Python 函数创建 LangChain 工具
        
        Args:
            func: Python 函数
            name: 工具名称（可选，默认使用函数名）
            description: 工具描述
            args_schema: 参数 Schema
            coroutine: 异步函数（可选）
        
        Returns:
            LangChain 工具实例
        
        Example:
            >>> def search_code(query: str) -> str:
            ...     return f"Results for: {query}"
            >>> tool = ToolAdapter.adapt_from_function(
            ...     search_code,
            ...     description="Search code in repository",
            ... )
        """
        tool_name = name or func.__name__
        
        return StructuredTool(
            name=tool_name,
            description=description or func.__doc__ or f"Tool: {tool_name}",
            func=func,
            coroutine=coroutine,
            args_schema=args_schema,
        )
    
    @staticmethod
    def _wrap_sync_to_async(sync_func: Callable, tool_instance: Any = None) -> Callable:
        """
        将同步函数包装为异步函数
        
        Args:
            sync_func: 同步函数
            tool_instance: 工具实例（可选，用于调用方法）
        
        Returns:
            异步包装函数
        """
        import asyncio
        import functools
        
        @functools.wraps(sync_func)
        async def async_wrapper(*args, **kwargs):
            # 在线程池中运行同步函数
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                functools.partial(sync_func, *args, **kwargs),
            )
        
        return async_wrapper


class SecureToolAdapter(ToolAdapter):
    """
    安全工具适配器
    
    在适配工具时添加权限检查和安全控制。
    """
    
    def __init__(self, permission_checker: Optional[Callable] = None):
        """
        初始化安全适配器
        
        Args:
            permission_checker: 权限检查函数
                签名: (agent_id: str, tool_name: str) -> bool
        """
        self.permission_checker = permission_checker
    
    def adapt_with_permission(
        self,
        tool: Any,
        agent_id: str,
        **kwargs,
    ) -> LangChainTool:
        """
        适配工具并添加权限检查
        
        Args:
            tool: IntelliTeam 工具实例
            agent_id: Agent ID
            **kwargs: 传递给 adapt() 的其他参数
        
        Returns:
            带权限检查的 LangChain 工具
        
        Raises:
            PermissionError: 如果没有权限
        """
        # 先适配工具
        langchain_tool = self.adapt(tool, **kwargs)
        tool_name = langchain_tool.name
        
        # 如果没有权限检查器，直接返回
        if not self.permission_checker:
            return langchain_tool
        
        # 包装原始执行函数
        original_func = langchain_tool.func
        original_coroutine = langchain_tool.coroutine
        
        def secure_func(*args, **kwargs):
            # 检查权限
            if not self.permission_checker(agent_id, tool_name):
                raise PermissionError(
                    f"Agent '{agent_id}' does not have permission to use tool '{tool_name}'"
                )
            # 执行原始函数
            return original_func(*args, **kwargs)
        
        async def secure_coroutine(*args, **kwargs):
            # 检查权限
            if not self.permission_checker(agent_id, tool_name):
                raise PermissionError(
                    f"Agent '{agent_id}' does not have permission to use tool '{tool_name}'"
                )
            # 执行原始异步函数
            if original_coroutine:
                return await original_coroutine(*args, **kwargs)
            else:
                return await self._wrap_sync_to_async(original_func)(*args, **kwargs)
        
        # 创建新的安全工具
        return StructuredTool(
            name=langchain_tool.name,
            description=langchain_tool.description,
            func=secure_func,
            coroutine=secure_coroutine,
            args_schema=langchain_tool.args_schema,
        )


# ============================================
# 便捷函数
# ============================================

def adapt_tool(tool: Any, **kwargs) -> LangChainTool:
    """
    便捷函数：适配单个工具
    
    Args:
        tool: IntelliTeam 工具实例
        **kwargs: 传递给 ToolAdapter.adapt() 的参数
    
    Returns:
        LangChain 工具实例
    """
    return ToolAdapter.adapt(tool, **kwargs)


def adapt_tools(tools: list[Any], **kwargs) -> list[LangChainTool]:
    """
    便捷函数：批量适配工具
    
    Args:
        tools: IntelliTeam 工具列表
        **kwargs: 传递给 ToolAdapter.adapt_batch() 的参数
    
    Returns:
        LangChain 工具列表
    """
    return ToolAdapter.adapt_batch(tools, **kwargs)


def adapt_tool_with_timeout(
    tool: Any,
    timeout: float,
    **kwargs,
) -> LangChainTool:
    """
    适配工具并添加超时控制
    
    Args:
        tool: IntelliTeam 工具实例
        timeout: 超时时间（秒）
        **kwargs: 传递给 ToolAdapter.adapt() 的参数
    
    Returns:
        带超时控制的 LangChain 工具实例
    
    Example:
        >>> from src.tools import CodeTools
        >>> tool = adapt_tool_with_timeout(CodeTools(), timeout=30.0)
    """
    # 先适配基本工具
    langchain_tool = ToolAdapter.adapt(tool, **kwargs)
    
    # 获取原始执行函数
    original_func = langchain_tool.func
    original_coroutine = langchain_tool.coroutine
    
    # 包装同步函数添加超时
    def timeout_func(*args, **kwargs_inner):
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError(f"Tool '{langchain_tool.name}' execution timed out after {timeout}s")
        
        # 设置信号处理器（仅在 Unix 系统上有效）
        try:
            old_handler = signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(int(timeout))
            try:
                result = original_func(*args, **kwargs_inner)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)
            return result
        except (AttributeError, ValueError):
            # Windows 不支持 SIGALRM，直接执行
            logger.warning("Timeout not supported on this platform, executing without timeout")
            return original_func(*args, **kwargs_inner)
    
    # 包装异步函数添加超时
    async def timeout_coroutine(*args, **kwargs_inner):
        try:
            if original_coroutine:
                return await asyncio.wait_for(
                    original_coroutine(*args, **kwargs_inner),
                    timeout=timeout
                )
            elif original_func:
                # 包装同步函数为异步
                return await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None,
                        functools.partial(original_func, *args, **kwargs_inner)
                    ),
                    timeout=timeout
                )
        except asyncio.TimeoutError:
            raise TimeoutError(f"Tool '{langchain_tool.name}' execution timed out after {timeout}s")
    
    # 创建带超时的工具
    return StructuredTool(
        name=langchain_tool.name,
        description=langchain_tool.description,
        func=timeout_func,
        coroutine=timeout_coroutine,
        args_schema=langchain_tool.args_schema,
    )


def adapt_tools_with_timeout(
    tools: list[Any],
    timeout: float,
    **kwargs,
) -> list[LangChainTool]:
    """
    批量适配工具并添加超时控制
    
    Args:
        tools: IntelliTeam 工具列表
        timeout: 超时时间（秒）
        **kwargs: 传递给 adapt_tool_with_timeout() 的参数
    
    Returns:
        带超时控制的 LangChain 工具列表
    """
    return [adapt_tool_with_timeout(tool, timeout, **kwargs) for tool in tools]
