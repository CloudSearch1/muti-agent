"""
ReAct 异常定义

定义 ReAct 系统中使用的自定义异常。
"""

from ..core.exceptions import AgentError


class ReActError(AgentError):
    """ReAct 错误基类"""
    
    def __init__(self, message: str, **kwargs):
        # 将额外参数存储到 details 中，而不是传递给父类
        super().__init__(
            message=message,
            code=kwargs.pop("code", "REACT_ERROR"),
            details=kwargs if kwargs else None
        )
        self.context = kwargs


class ReActMaxIterationsError(ReActError):
    """
    达到最大迭代次数错误
    
    当 ReAct 循环达到最大迭代次数但未得出结论时抛出。
    """
    
    def __init__(self, iterations: int, last_thought: str = ""):
        super().__init__(
            f"ReAct agent reached maximum iterations ({iterations}) without conclusion",
            iterations=iterations,
            last_thought=last_thought,
        )
        self.iterations = iterations
        self.last_thought = last_thought


class ReActTimeoutError(ReActError):
    """
    执行超时错误
    
    当 ReAct 执行超过最大允许时间时抛出。
    """
    
    def __init__(self, timeout: float, elapsed: float):
        super().__init__(
            f"ReAct execution timed out after {elapsed:.2f}s (limit: {timeout}s)",
            timeout=timeout,
            elapsed=elapsed,
        )
        self.timeout = timeout
        self.elapsed = elapsed


class ReActToolExecutionError(ReActError):
    """
    工具执行错误
    
    当工具执行失败时抛出。
    """
    
    def __init__(self, tool_name: str, error: str, tool_input: dict | None = None):
        super().__init__(
            f"Tool '{tool_name}' execution failed: {error}",
            tool_name=tool_name,
            error=error,
            tool_input=tool_input,
        )
        self.tool_name = tool_name
        self.error = error
        self.tool_input = tool_input


class ReActLoopDetectedError(ReActError):
    """
    循环检测错误
    
    当检测到 ReAct 陷入无限循环时抛出。
    """
    
    def __init__(self, action: str, count: int):
        super().__init__(
            f"Detected infinite loop: action '{action}' repeated {count} times",
            action=action,
            count=count,
        )
        self.action = action
        self.count = count


class ReActParsingError(ReActError):
    """
    输出解析错误
    
    当 LLM 输出无法解析为 ReAct 格式时抛出。
    """
    
    def __init__(self, output: str, expected_format: str = "ReAct"):
        super().__init__(
            f"Failed to parse LLM output as {expected_format} format",
            output=output,
            expected_format=expected_format,
        )
        self.output = output
        self.expected_format = expected_format
