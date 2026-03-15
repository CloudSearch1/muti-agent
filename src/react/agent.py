"""
ReAct Agent 基类

实现基于 LangChain/LangGraph 的 ReAct (Reasoning + Acting) Agent。
"""

import asyncio
import time
from datetime import datetime
from typing import Any, Optional, List, Dict

from langchain.tools import BaseTool as LangChainTool
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
import structlog

# 初始化标志
USE_LANGGRAPH = False
USE_LEGACY = False

# 尝试导入 LangGraph (LangChain 1.0+)
try:
    from langgraph.prebuilt import create_react_agent as langgraph_create_react_agent
    USE_LANGGRAPH = True
except ImportError:
    pass

# 尝试导入 Legacy AgentExecutor
# LangChain 1.0+ 将旧版 Agent 移到了 langchain_classic
try:
    # 首先尝试从 langchain_classic 导入 (LangChain 1.0+)
    from langchain_classic.agents import AgentExecutor
    from langchain_classic.agents import create_react_agent as legacy_create_react_agent
    USE_LEGACY = True
except ImportError:
    # 如果失败，尝试从 langchain.agents 导入 (旧版本)
    try:
        from langchain.agents import AgentExecutor
        from langchain.agents import create_react_agent as legacy_create_react_agent
        USE_LEGACY = True
    except ImportError:
        pass

# 如果 LangGraph 和 Legacy 都不可用，需要至少有一个
if not USE_LANGGRAPH and not USE_LEGACY:
    raise ImportError("No compatible agent framework found. Please install langgraph or langchain.")

from ..agents.base import BaseAgent
from ..core.exceptions import AgentExecutionError
from ..core.models import AgentRole, Blackboard, Task
from .callbacks import LoopDetectionCallback, MetricsCallbackHandler, ReActCallbackHandler
from .exceptions import (
    ReActError,
    ReActMaxIterationsError,
    ReActTimeoutError,
    ReActLoopDetectedError,
)
from .prompts import get_default_react_prompt, get_role_specific_prompt
from .types import ReActConfig, ReActResult, ReActStep

logger = structlog.get_logger(__name__)


class ReActAgent(BaseAgent):
    """
    ReAct Agent 基类
    
    基于 LangChain/LangGraph 的 ReAct Agent 实现，支持：
    - 自动推理循环（Thought-Action-Observation）
    - 异步执行
    - 完整的推理链记录
    - 工具调用监控
    - 循环检测
    - 性能指标收集
    
    使用示例：
        >>> from src.react import ReActAgent
        >>> from langchain_openai import ChatOpenAI
        >>> from langchain.tools import Tool
        >>> 
        >>> llm = ChatOpenAI(model="gpt-4")
        >>> tools = [Tool(name="search", func=search_func, description="Search")]
        >>> 
        >>> agent = ReActAgent(
        ...     agent_id="react-001",
        ...     role=AgentRole.DEVELOPER,
        ...     llm=llm,
        ...     tools=tools,
        ...     config=ReActConfig(max_iterations=10)
        ... )
        >>> 
        >>> async with agent.lifecycle():
        ...     result = await agent.process_task(task)
        ...     print(result.output_data["reasoning_chain"])
    """
    
    def __init__(
        self,
        agent_id: str,
        role: AgentRole,
        llm: BaseChatModel,
        tools: Optional[List[LangChainTool]] = None,
        config: Optional[ReActConfig] = None,
        prompt_template: Optional[str] = None,
        force_legacy: bool = False,
        extra_callbacks: Optional[List[Any]] = None,
        **kwargs
    ):
        """
        初始化 ReAct Agent
        
        Args:
            agent_id: Agent ID
            role: Agent 角色
            llm: LLM 模型
            tools: LangChain 工具列表
            config: ReAct 配置
            prompt_template: 自定义 Prompt 模板（可选）
            force_legacy: 强制使用 Legacy 模式（适用于不支持原生 function calling 的模型）
            extra_callbacks: 额外的回调处理器列表（可选）
            **kwargs: 其他参数传递给 BaseAgent
        """
        super().__init__(agent_id=agent_id, role=role, **kwargs)
        
        self.llm = llm
        self.tools = tools or []
        self.config = config or ReActConfig()
        self.prompt_template = prompt_template
        self.force_legacy = force_legacy
        self.extra_callbacks = extra_callbacks or []
        
        # 初始化回调处理器
        self._init_callbacks()
        
        # 创建 agent 执行器
        self._executor = None
        self._setup_executor()
        
        # 推理链记录
        self._reasoning_chain: List[Dict] = []
        self._current_iteration = 0
        
        logger.info(
            "ReAct Agent initialized",
            agent_id=agent_id,
            role=role.value if hasattr(role, 'value') else str(role),
            tools_count=len(self.tools),
            use_langgraph=USE_LANGGRAPH
        )
    
    def _init_callbacks(self):
        """初始化回调处理器"""
        # 主回调处理器 - 记录推理链
        self._react_callback = ReActCallbackHandler(
            verbose=self.config.verbose,
            log_to_console=self.config.verbose,
        )
        
        # 循环检测回调
        self._loop_callback = None
        if self.config.enable_loop_detection:
            self._loop_callback = LoopDetectionCallback(
                max_same_action=self.config.max_same_action,
                max_same_input=self.config.max_same_action,
                raise_on_loop=True,
            )
        
        # 性能指标回调
        self._metrics_callback = MetricsCallbackHandler()
        
        # 收集所有回调
        self._callbacks = [self._react_callback, self._metrics_callback]
        if self._loop_callback:
            self._callbacks.append(self._loop_callback)
        
        # 添加额外的回调（例如实时进展推送）
        if self.extra_callbacks:
            self._callbacks.extend(self.extra_callbacks)
    
    def _reset_callbacks(self):
        """重置回调处理器状态"""
        self._react_callback.reset()
        self._metrics_callback = MetricsCallbackHandler()
        if self._loop_callback:
            self._loop_callback.reset()
    
    def _setup_executor(self):
        """设置 Agent 执行器"""
        try:
            # 获取合适的 prompt
            prompt = self._get_prompt()
            
            # 决定使用哪种执行器
            # 如果 force_legacy 为 True，强制使用 Legacy 模式
            # LangGraph 需要模型支持原生 function calling，百炼等兼容 API 可能不支持
            use_langgraph = USE_LANGGRAPH and not self.force_legacy
            
            if use_langgraph:
                # 使用 LangGraph (新版)
                # LangGraph 不支持直接传入 prompt，需要通过 system message
                self._system_prompt = self._extract_system_prompt(prompt)
                self._executor = langgraph_create_react_agent(
                    model=self.llm,
                    tools=self.tools,
                )
                logger.debug("Using LangGraph executor")
            elif USE_LEGACY:
                # 使用旧版 AgentExecutor
                agent = legacy_create_react_agent(
                    llm=self.llm,
                    tools=self.tools,
                    prompt=prompt
                )
                self._executor = AgentExecutor(
                    agent=agent,
                    tools=self.tools,
                    max_iterations=self.config.max_iterations,
                    max_execution_time=self.config.max_execution_time,
                    # 处理解析错误：返回更详细的错误信息指导 LLM
                    handle_parsing_errors=True,  # 使用默认错误处理，会包含原始输出
                    verbose=self.config.verbose,
                    callbacks=self._callbacks,  # 注册回调
                )
                logger.debug("Using legacy AgentExecutor")
            else:
                raise ReActError("No compatible agent framework found")
                
        except Exception as e:
            logger.error("Failed to setup executor", error=str(e))
            raise ReActError(f"Failed to setup agent executor: {e}")
    
    def _get_prompt(self):
        """获取 Prompt 模板"""
        if self.prompt_template:
            from langchain_core.prompts import PromptTemplate
            return PromptTemplate.from_template(self.prompt_template)
        
        # 根据角色获取对应的 prompt
        role_name = self.ROLE.value if hasattr(self, 'ROLE') and self.ROLE else "default"
        role_name_lower = role_name.lower() if isinstance(role_name, str) else "default"
        
        return get_role_specific_prompt(role_name_lower)
    
    def _extract_system_prompt(self, prompt) -> str:
        """从 PromptTemplate 中提取系统提示"""
        if hasattr(prompt, 'template'):
            return prompt.template
        return str(prompt)
    
    async def think(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        ReAct Agent 的思考过程
        
        Args:
            context: 上下文信息
            
        Returns:
            思考结果
        """
        context = context or {}
        return {
            "thought": "Processing context",
            "context": context,
            "available_tools": [t.name for t in self.tools],
        }
    
    async def execute(self, task: Task) -> Any:
        """
        执行 ReAct 推理循环
        
        Args:
            task: 任务对象
            
        Returns:
            执行结果
        """
        start_time = time.time()
        
        # 重置状态
        self._reasoning_chain = []
        self._current_iteration = 0
        self._reset_callbacks()
        
        try:
            # 准备输入
            input_text = task.description
            
            # 使用 input_data 作为上下文（Task 模型中定义的字段）
            if task.input_data:
                # 构建更清晰的上下文格式
                context_parts = []
                
                # 处理历史对话（如果存在）
                if "history" in task.input_data:
                    history = task.input_data["history"]
                    if history and history.strip():
                        context_parts.append(f"## 历史对话\n{history}")
                
                # 处理其他上下文信息（排除 history）
                other_context = {k: v for k, v in task.input_data.items() if k != "history"}
                if other_context:
                    other_context_str = "\n".join([f"- {k}: {v}" for k, v in other_context.items()])
                    context_parts.append(f"## 会话信息\n{other_context_str}")
                
                # 组合上下文和任务
                if context_parts:
                    context_str = "\n\n".join(context_parts)
                    input_text = f"{context_str}\n\n## 当前任务\n{task.description}"
            
            logger.info("Starting ReAct execution", task_id=task.id, input_length=len(input_text))
            
            # 执行 Agent
            # 根据实际使用的 executor 类型选择执行方法
            if hasattr(self._executor, 'ainvoke'):
                # 检查 executor 类型
                executor_type = type(self._executor).__name__
                
                if executor_type == "CompiledGraph":
                    # LangGraph executor
                    result = await self._execute_with_langgraph(input_text, task)
                else:
                    # Legacy AgentExecutor
                    result = await self._execute_with_legacy(input_text, task)
            else:
                # 默认使用 Legacy
                result = await self._execute_with_legacy(input_text, task)
            
            # 计算执行时间
            execution_time = time.time() - start_time
            
            # 从回调中获取推理链
            self._reasoning_chain = self._react_callback.get_reasoning_chain()
            self._current_iteration = len(self._reasoning_chain)
            
            # 获取性能指标
            metrics = self._metrics_callback.get_metrics()
            
            # 构建结果
            return {
                "output": result,
                "reasoning_chain": self._reasoning_chain,
                "iterations": self._current_iteration,
                "total_execution_time": execution_time,
                "success": True,
                "metrics": metrics,
            }
            
        except ReActLoopDetectedError as e:
            # 循环检测异常
            execution_time = time.time() - start_time
            logger.warning(
                "ReAct loop detected",
                task_id=task.id,
                action=e.action if hasattr(e, 'action') else "unknown",
            )
            return {
                "output": f"Execution stopped due to loop detection: {e}",
                "reasoning_chain": self._reasoning_chain,
                "iterations": self._current_iteration,
                "total_execution_time": execution_time,
                "success": False,
                "error": str(e),
                "error_type": "loop_detected",
            }
        except ReActTimeoutError as e:
            # 超时异常
            execution_time = time.time() - start_time
            logger.warning(
                "ReAct execution timed out",
                task_id=task.id,
                timeout_seconds=self.config.max_execution_time or 300.0,
            )
            return {
                "output": f"Execution timed out: {e}",
                "reasoning_chain": self._reasoning_chain,
                "iterations": self._current_iteration,
                "total_execution_time": execution_time,
                "success": False,
                "error": str(e),
                "error_type": "timeout",
            }
        except Exception as e:
            logger.error("ReAct execution failed", error=str(e), exc_info=True)
            raise ReActError(f"ReAct execution failed: {e}")
    
    async def _execute_with_langgraph(self, input_text: str, task: Task) -> str:
        """
        使用 LangGraph 执行
        
        LangGraph 模式下，我们不需要手动构建 system prompt，
        LangGraph 会自动处理工具调用和 prompt。
        """
        try:
            # LangGraph 直接使用消息列表
            messages = [HumanMessage(content=input_text)]
            
            # 配置参数
            config = {
                "callbacks": self._callbacks,  # 注册回调
            }
            
            logger.info("Invoking LangGraph executor", message_count=len(messages))
            
            # 添加超时控制
            try:
                result = await asyncio.wait_for(
                    self._executor.ainvoke(
                        {"messages": messages},
                        config=config,
                    ),
                    timeout=self.config.max_execution_time or 300.0,
                )
            except asyncio.TimeoutError:
                logger.error("LangGraph execution timed out")
                raise ReActTimeoutError(
                    f"Execution timed out after {self.config.max_execution_time or 300.0} seconds"
                )
            
            logger.info("LangGraph execution completed", result_type=type(result).__name__)
            
            # 安全处理 result（可能是 dict 或其他类型）
            if not isinstance(result, dict):
                logger.warning(f"Unexpected LangGraph result type: {type(result)}")
                return str(result)
            
            # 从 LangGraph 结果中提取推理链
            if "messages" in result:
                messages_result = result["messages"]
                if isinstance(messages_result, list):
                    self._extract_reasoning_from_messages(messages_result)
                    
                    # 提取最终响应
                    if messages_result:
                        last_message = messages_result[-1]
                        if hasattr(last_message, "content"):
                            return last_message.content
            
            return str(result)
            
        except Exception as e:
            logger.error("LangGraph execution failed", error=str(e))
            raise
    
    def _extract_reasoning_from_messages(self, messages: List):
        """
        从 LangGraph 消息列表中提取推理链
        
        Args:
            messages: LangGraph 返回的消息列表
        """
        for i, msg in enumerate(messages):
            # 跳过第一轮的系统消息和用户消息
            if isinstance(msg, SystemMessage):
                continue
            if isinstance(msg, HumanMessage):
                continue
            
            # 处理 AI 消息（包含工具调用）
            if isinstance(msg, AIMessage):
                # 检查是否有工具调用
                if hasattr(msg, 'tool_calls') and msg.tool_calls:
                    for tool_call in msg.tool_calls:
                        step = {
                            "thought": msg.content or "",
                            "action": tool_call.get("name", "unknown"),
                            "action_input": tool_call.get("args", {}),
                            "timestamp": datetime.now().isoformat(),
                        }
                        self._reasoning_chain.append(step)
                elif msg.content:
                    # 纯思考步骤 - 也记录到推理链
                    step = {
                        "thought": msg.content,
                        "action": None,  # 标记为纯思考
                        "action_input": None,
                        "observation": None,
                        "timestamp": datetime.now().isoformat(),
                        "step_type": "thought",  # 标记步骤类型
                    }
                    self._reasoning_chain.append(step)
                    self._current_iteration += 1
            
            # 处理工具消息（工具返回结果）
            elif isinstance(msg, ToolMessage):
                # 将结果关联到上一个步骤
                if self._reasoning_chain:
                    last_step = self._reasoning_chain[-1]
                    last_step["observation"] = msg.content
                    self._current_iteration += 1
    
    async def _execute_with_legacy(self, input_text: str, task: Task) -> str:
        """使用旧版 AgentExecutor 执行"""
        try:
            # 使用回调配置
            config = {
                "callbacks": self._callbacks,
            }
            
            logger.info("Invoking legacy AgentExecutor", input_length=len(input_text))
            
            # 添加超时保护
            try:
                result = await asyncio.wait_for(
                    self._executor.ainvoke(
                        {"input": input_text},
                        config=config,
                    ),
                    timeout=self.config.max_execution_time or 300.0,
                )
            except asyncio.TimeoutError:
                logger.error("Legacy executor timed out")
                raise ReActTimeoutError(
                    f"Execution timed out after {self.config.max_execution_time or 300.0} seconds"
                )
            
            logger.info("Legacy executor completed", result_type=type(result).__name__)
            
            # 安全处理 result（可能是 dict 或其他类型）
            if not isinstance(result, dict):
                logger.warning(f"Unexpected result type: {type(result)}, converting to string")
                return str(result)
            
            # 从 intermediate_steps 中提取推理链
            intermediate_steps = result.get("intermediate_steps", [])
            logger.info("Extracting reasoning chain", steps_count=len(intermediate_steps))
            
            for action, observation in intermediate_steps:
                step = {
                    "thought": getattr(action, 'log', ''),
                    "action": getattr(action, 'tool', 'unknown'),
                    "action_input": getattr(action, 'tool_input', {}),
                    "observation": str(observation),
                    "timestamp": datetime.now().isoformat(),
                }
                self._reasoning_chain.append(step)
                self._current_iteration += 1
            
            output = result.get("output", str(result))
            logger.info("Legacy executor output", output_length=len(output))
            
            return output
            
        except Exception as e:
            logger.error("Legacy executor failed", error=str(e), exc_info=True)
            raise
    
    async def process_task(self, task: Task) -> Task:
        """
        处理任务（实现 BaseAgent 接口）
        
        Args:
            task: 任务对象
            
        Returns:
            更新后的任务对象
        """
        # 执行推理循环
        execution_result = await self.execute(task)
        
        # 更新任务状态和输出数据
        task.status = "completed" if execution_result.get("success") else "failed"
        task.completed_at = datetime.now()
        task.output_data = execution_result
        
        return task
