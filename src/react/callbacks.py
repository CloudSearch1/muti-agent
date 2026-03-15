"""
ReAct 回调处理器

提供执行监控、推理链记录、循环检测等回调功能。
"""

from collections import deque
from datetime import datetime
from typing import Any, Optional

# 修复 LangChain 新版本的导入路径
try:
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError:
    try:
        from langchain.callbacks.base import BaseCallbackHandler
    except ImportError:
        # 如果都不可用，创建一个基础的回调类
        class BaseCallbackHandler:
            """Fallback callback handler"""
            pass

from langchain_core.outputs import LLMResult

import structlog

from .exceptions import ReActLoopDetectedError
from .types import ReActStep

logger = structlog.get_logger(__name__)


class ReActCallbackHandler(BaseCallbackHandler):
    """
    ReAct 执行回调处理器
    
    功能：
    1. 记录推理链（Thought-Action-Observation）
    2. 监控执行性能
    3. 实时反馈
    """
    
    def __init__(
        self,
        verbose: bool = False,
        log_to_console: bool = False,
    ):
        """
        初始化回调处理器
        
        Args:
            verbose: 是否详细日志
            log_to_console: 是否输出到控制台
        """
        self.verbose = verbose
        self.log_to_console = log_to_console
        
        # 推理步骤记录
        self.reasoning_steps: list[ReActStep] = []
        
        # 当前步骤
        self.current_step: Optional[ReActStep] = None
        
        # 执行统计
        self.start_time: Optional[datetime] = None
        self.llm_calls = 0
        self.tool_calls = 0
        self.total_tokens = 0
    
    def on_llm_start(
        self,
        serialized: dict,
        prompts: list[str],
        **kwargs: Any,
    ) -> None:
        """LLM 开始生成"""
        self.llm_calls += 1
        
        if self.start_time is None:
            self.start_time = datetime.now()
        
        logger.debug(
            "LLM call started",
            call_number=self.llm_calls,
            prompt_count=len(prompts),
        )
    
    def on_llm_end(
        self,
        response: LLMResult,
        **kwargs: Any,
    ) -> None:
        """LLM 生成结束"""
        # 记录 token 使用
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            self.total_tokens += usage.get("total_tokens", 0)
        
        logger.debug(
            "LLM call ended",
            total_tokens=self.total_tokens,
        )
    
    def on_tool_start(
        self,
        serialized: dict,
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """工具开始执行"""
        self.tool_calls += 1
        tool_name = serialized.get("name", "unknown")
        
        # 创建新的推理步骤
        self.current_step = ReActStep(
            thought="",
            action=tool_name,
            action_input={"input": input_str} if input_str else {},
        )
        
        if self.log_to_console:
            print(f"\n[Tool Start] {tool_name}")
            print(f"  Input: {input_str}")
        
        logger.info(
            "Tool execution started",
            tool_name=tool_name,
            tool_input=input_str,
            call_number=self.tool_calls,
        )
    
    def on_tool_end(
        self,
        output: str,
        **kwargs: Any,
    ) -> None:
        """工具执行结束"""
        if self.current_step:
            self.current_step.observation = output
            
            # 计算执行时间
            if self.start_time:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                self.current_step.execution_time = elapsed
            
            # 添加到推理链
            self.reasoning_steps.append(self.current_step)
            
            if self.log_to_console:
                print(f"\n[Tool End] {self.current_step.action}")
                print(f"  Output: {output[:200]}..." if len(output) > 200 else f"  Output: {output}")
            
            logger.info(
                "Tool execution completed",
                tool_name=self.current_step.action,
                output_length=len(output),
            )
            
            self.current_step = None
    
    def on_tool_error(
        self,
        error: Exception | str,
        **kwargs: Any,
    ) -> None:
        """工具执行错误"""
        error_msg = str(error)
        
        if self.current_step:
            self.current_step.observation = f"Error: {error_msg}"
            self.reasoning_steps.append(self.current_step)
            self.current_step = None
        
        if self.log_to_console:
            print(f"\n[Tool Error] {error_msg}")
        
        logger.error(
            "Tool execution failed",
            error=error_msg,
            error_type=type(error).__name__,
        )
    
    def on_chain_start(
        self,
        serialized: dict,
        inputs: dict,
        **kwargs: Any,
    ) -> None:
        """链开始执行"""
        # 只记录 AgentExecutor 级别的 chain（过滤内部 Prompt 格式化等）
        # 通过检查 inputs 是否包含 'input' 键来判断是否是 AgentExecutor
        if inputs and 'input' in inputs:
            # 截断过长的输入，避免日志过于冗长
            input_str = str(inputs.get('input', ''))[:200]
            logger.info("ReAct AgentExecutor started", input_preview=input_str)
    
    def on_chain_end(
        self,
        outputs: dict | list,
        **kwargs: Any,
    ) -> None:
        """链执行结束"""
        # 只记录 AgentExecutor 级别的 chain 结束
        # 通过检查 outputs 是否包含 'output' 键来判断是否是 AgentExecutor 结果
        if isinstance(outputs, dict):
            # AgentExecutor 结果通常包含 'output' 和 'intermediate_steps'
            if 'output' in outputs or 'intermediate_steps' in outputs:
                output_preview = str(outputs.get('output', ''))[:200]
                steps_count = len(outputs.get('intermediate_steps', []))
                logger.info(
                    "ReAct AgentExecutor completed",
                    output_preview=output_preview,
                    intermediate_steps=steps_count,
                )
        # 忽略其他类型的 chain 结束（如 StringPromptValue 等）
    
    def get_reasoning_chain(self) -> list[dict[str, Any]]:
        """
        获取推理链（字典格式）
        
        Returns:
            推理步骤列表
        """
        return [step.to_dict() for step in self.reasoning_steps]
    
    def get_statistics(self) -> dict[str, Any]:
        """
        获取执行统计信息
        
        Returns:
            统计数据字典
        """
        if self.start_time:
            total_time = (datetime.now() - self.start_time).total_seconds()
        else:
            total_time = 0.0
        
        return {
            "llm_calls": self.llm_calls,
            "tool_calls": self.tool_calls,
            "total_tokens": self.total_tokens,
            "total_time": total_time,
            "steps": len(self.reasoning_steps),
        }
    
    def reset(self) -> None:
        """重置回调状态"""
        self.reasoning_steps = []
        self.current_step = None
        self.start_time = None
        self.llm_calls = 0
        self.tool_calls = 0
        self.total_tokens = 0


class LoopDetectionCallback(BaseCallbackHandler):
    """
    循环检测回调
    
    检测 ReAct 执行过程中是否陷入无限循环。
    """
    
    def __init__(
        self,
        max_same_action: int = 3,
        max_same_input: int = 2,
        raise_on_loop: bool = True,
    ):
        """
        初始化循环检测回调
        
        Args:
            max_same_action: 相同动作的最大重复次数
            max_same_input: 相同输入的最大重复次数
            raise_on_loop: 是否在检测到循环时抛出异常
        """
        self.max_same_action = max_same_action
        self.max_same_input = max_same_input
        self.raise_on_loop = raise_on_loop
        
        # 动作历史
        self.action_history: deque = deque(maxlen=100)
        
        # 循环检测标志
        self.loop_detected = False
        self.loop_reason = ""
    
    def on_tool_start(
        self,
        serialized: dict,
        input_str: str,
        **kwargs: Any,
    ) -> None:
        """工具开始执行时检测循环"""
        tool_name = serialized.get("name", "unknown")
        
        # 构造动作标识
        action_key = f"{tool_name}:{input_str}"
        action_only = f"{tool_name}"
        
        # 检测相同动作+输入的循环
        # 统计当前 action_key 在历史记录中出现的次数
        same_action_count = sum(1 for a in self.action_history if a == action_key)
        if same_action_count >= self.max_same_input:
            self.loop_detected = True
            self.loop_reason = f"Same action with same input repeated {same_action_count + 1} times: {action_key}"
            
            logger.warning(
                "Loop detected",
                reason=self.loop_reason,
                action=action_key,
            )
            
            if self.raise_on_loop:
                raise ReActLoopDetectedError(
                    action=action_key,
                    count=same_action_count + 1,
                )
        
        # 检测相同动作的循环（忽略输入差异）
        # 统计最近连续相同工具的次数
        recent_actions = [a.split(":")[0] for a in self.action_history]
        consecutive_same_count = 0
        for action in reversed(recent_actions):
            if action == tool_name:
                consecutive_same_count += 1
            else:
                break
        
        if consecutive_same_count >= self.max_same_action - 1:
            self.loop_detected = True
            self.loop_reason = f"Same action repeated {consecutive_same_count + 1} times (with different inputs): {tool_name}"
            
            logger.warning(
                "Loop detected",
                reason=self.loop_reason,
                action=tool_name,
            )
            
            if self.raise_on_loop:
                raise ReActLoopDetectedError(
                    action=tool_name,
                    count=consecutive_same_count + 1,
                )
        
        # 记录动作
        self.action_history.append(action_key)
    
    def reset(self) -> None:
        """重置检测状态"""
        self.action_history.clear()
        self.loop_detected = False
        self.loop_reason = ""
    
    def is_looping(self) -> bool:
        """是否检测到循环"""
        return self.loop_detected
    
    def get_loop_reason(self) -> str:
        """获取循环原因"""
        return self.loop_reason


class StreamingCallbackHandler(BaseCallbackHandler):
    """
    流式输出回调
    
    用于实时输出 LLM 生成的文本。
    """
    
    def __init__(self, output_func: Optional[callable] = None):
        """
        初始化流式回调
        
        Args:
            output_func: 输出函数，默认为 print
        """
        self.output_func = output_func or print
    
    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:
        """LLM 生成新 token"""
        self.output_func(token, end="", flush=True)


class MetricsCallbackHandler(BaseCallbackHandler):
    """
    指标收集回调
    
    收集执行过程中的性能指标。
    """
    
    def __init__(self):
        """初始化指标收集器"""
        self.metrics = {
            "llm_calls": 0,
            "tool_calls": 0,
            "total_tokens": 0,
            "total_time": 0.0,
            "errors": 0,
        }
        self.start_time: Optional[datetime] = None
        self.tool_times: dict[str, list[float]] = {}
    
    def on_llm_start(self, serialized: dict, prompts: list, **kwargs: Any) -> None:
        """LLM 开始"""
        if self.start_time is None:
            self.start_time = datetime.now()
        self.metrics["llm_calls"] += 1
    
    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """LLM 结束"""
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            self.metrics["total_tokens"] += usage.get("total_tokens", 0)
    
    def on_tool_start(self, serialized: dict, input_str: str, **kwargs: Any) -> None:
        """工具开始"""
        self.metrics["tool_calls"] += 1
        self._current_tool = serialized.get("name", "unknown")
        self._tool_start_time = datetime.now()
    
    def on_tool_end(self, output: str, **kwargs: Any) -> None:
        """工具结束"""
        if hasattr(self, "_current_tool") and hasattr(self, "_tool_start_time"):
            elapsed = (datetime.now() - self._tool_start_time).total_seconds()
            
            if self._current_tool not in self.tool_times:
                self.tool_times[self._current_tool] = []
            self.tool_times[self._current_tool].append(elapsed)
    
    def on_tool_error(self, error: Exception | str, **kwargs: Any) -> None:
        """工具错误"""
        self.metrics["errors"] += 1
    
    def get_metrics(self) -> dict[str, Any]:
        """获取指标"""
        if self.start_time:
            self.metrics["total_time"] = (
                datetime.now() - self.start_time
            ).total_seconds()
        
        # 计算工具平均执行时间
        tool_avg_times = {}
        for tool_name, times in self.tool_times.items():
            tool_avg_times[tool_name] = {
                "avg": sum(times) / len(times),
                "min": min(times),
                "max": max(times),
                "count": len(times),
            }
        
        return {
            **self.metrics,
            "tool_times": tool_avg_times,
        }
