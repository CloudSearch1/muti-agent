"""
ReAct 类型定义

定义 ReAct 系统使用的核心数据类型。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class ReActStep:
    """
    ReAct 单步执行记录
    
    记录一次 Thought-Action-Observation 循环的完整信息。
    """
    
    thought: str
    """思考内容"""
    
    action: Optional[str] = None
    """执行的工具名称"""
    
    action_input: Optional[dict[str, Any]] = None
    """工具输入参数"""
    
    observation: Optional[str] = None
    """工具执行结果（观察）"""
    
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    """时间戳"""
    
    execution_time: Optional[float] = None
    """执行耗时（秒）"""
    
    metadata: dict[str, Any] = field(default_factory=dict)
    """额外元数据"""
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "thought": self.thought,
            "action": self.action,
            "action_input": self.action_input,
            "observation": self.observation,
            "timestamp": self.timestamp,
            "execution_time": self.execution_time,
            "metadata": self.metadata,
        }


@dataclass
class ReActResult:
    """
    ReAct 执行结果
    
    包含最终答案和完整的推理链。
    """
    
    output: str
    """最终答案"""
    
    reasoning_chain: list[ReActStep] = field(default_factory=list)
    """推理链（所有步骤）"""
    
    iterations: int = 0
    """总迭代次数"""
    
    total_execution_time: float = 0.0
    """总执行时间（秒）"""
    
    success: bool = True
    """是否成功"""
    
    error: Optional[str] = None
    """错误信息"""
    
    metadata: dict[str, Any] = field(default_factory=dict)
    """额外元数据"""
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "output": self.output,
            "reasoning_chain": [step.to_dict() for step in self.reasoning_chain],
            "iterations": self.iterations,
            "total_execution_time": self.total_execution_time,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata,
        }
    
    def get_thoughts(self) -> list[str]:
        """获取所有思考内容"""
        return [step.thought for step in self.reasoning_chain]
    
    def get_actions(self) -> list[tuple[str, dict]]:
        """获取所有行动（工具名 + 参数）"""
        return [
            (step.action, step.action_input)
            for step in self.reasoning_chain
            if step.action
        ]
    
    def get_observations(self) -> list[str]:
        """获取所有观察结果"""
        return [
            step.observation
            for step in self.reasoning_chain
            if step.observation
        ]


@dataclass
class ReActConfig:
    """
    ReAct Agent 配置
    
    配置 ReAct Agent 的行为参数。
    """
    
    max_iterations: int = 10
    """最大迭代次数"""
    
    max_execution_time: Optional[float] = None
    """最大执行时间（秒），None 表示无限制"""
    
    early_stopping_method: str = "generate"
    """提前停止方法: 'generate' 或 'force'"""
    
    handle_parsing_errors: bool = True
    """是否处理解析错误"""
    
    verbose: bool = False
    """是否输出详细日志"""
    
    enable_loop_detection: bool = True
    """是否启用循环检测"""
    
    max_same_action: int = 3
    """循环检测：相同动作的最大重复次数"""
    
    timeout_per_tool: Optional[float] = None
    """单个工具执行超时（秒）"""
    
    stream_output: bool = False
    """是否流式输出"""
    
    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "max_iterations": self.max_iterations,
            "max_execution_time": self.max_execution_time,
            "early_stopping_method": self.early_stopping_method,
            "handle_parsing_errors": self.handle_parsing_errors,
            "verbose": self.verbose,
            "enable_loop_detection": self.enable_loop_detection,
            "max_same_action": self.max_same_action,
            "timeout_per_tool": self.timeout_per_tool,
            "stream_output": self.stream_output,
        }
