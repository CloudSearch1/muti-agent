"""
LangGraph 工作流编排（增强版）

职责：使用 LangGraph 编排多 Agent 协同工作流

增强功能：
- 状态转换验证
- 错误恢复机制
- 超时控制
- 进度追踪
- 并行执行支持
- 依赖注入支持（v2.0.0 新增）
- 灵活的任务依赖管理（v2.0.0 新增，从 executor.py 迁移）
- 事件处理器机制（v2.0.0 新增，从 executor.py 迁移）

版本：2.1.0
更新时间：2026-03-12
变更：
- 合并 src/core/executor.py 功能
- 添加 WorkflowTask 和 WorkflowDefinition 支持
- 支持灵活的任务依赖和并行执行
- 统一工作流执行接口
"""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

import structlog

from src.utils.compat import StrEnum

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = "__end__"

# 依赖注入：从容器获取 Agent，而非直接导入具体类
from ..core.container import AgentContainer, get_agent_container
from ..core.models import Task, TaskStatus
from .states import AgentState

logger = structlog.get_logger(__name__)


# 定义节点类型
NodeType = Literal[
    "start",
    "planner",
    "analyst",
    "architect",
    "coder",
    "tester",
    "doc_writer",
    "end",
]


# ===========================================
# 工作流任务定义（从 executor.py 迁移）
# ===========================================


@dataclass
class WorkflowTask:
    """
    工作流中的任务
    
    支持灵活的依赖关系定义和并行执行
    
    Attributes:
        agent_name: Agent 名称
        task_description: 任务描述
        dependencies: 依赖的任务索引列表
        timeout_seconds: 超时时间（秒）
        retry_count: 重试次数
        status: 任务状态
        result: 执行结果
        error: 错误信息
        started_at: 开始时间
        completed_at: 完成时间
    """
    agent_name: str
    task_description: str
    dependencies: list[str] = field(default_factory=list)
    timeout_seconds: int = 300
    retry_count: int = 3
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


@dataclass
class WorkflowDefinition:
    """
    工作流定义
    
    用于定义灵活的工作流结构，支持复杂的依赖关系
    
    Attributes:
        name: 工作流名称
        description: 工作流描述
        tasks: 任务列表
        status: 工作流状态
        created_at: 创建时间
        started_at: 开始时间
        completed_at: 完成时间
        metadata: 元数据
    """
    name: str
    description: str
    tasks: list[WorkflowTask] = field(default_factory=list)
    status: "WorkflowStatus" = None  # 将在后面定义
    created_at: datetime = field(default_factory=datetime.now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.status is None:
            self.status = WorkflowStatus.PENDING


class WorkflowStatus(StrEnum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class WorkflowProgress:
    """工作流进度追踪器"""

    def __init__(self, total_steps: int = 6):
        self.total_steps = total_steps
        self.current_step = 0
        self.step_names = ["start", "planner", "architect", "coder", "tester", "doc_writer", "end"]
        self.start_time: float | None = None
        self.end_time: float | None = None
        self.step_times: dict[str, float] = {}

    def start(self) -> None:
        """开始计时"""
        self.start_time = time.time()

    def complete(self) -> None:
        """完成计时"""
        self.end_time = time.time()

    def advance(self, step_name: str) -> None:
        """前进一步"""
        self.current_step = self.step_names.index(step_name) if step_name in self.step_names else self.current_step + 1
        self.step_times[step_name] = time.time()

    @property
    def progress_percent(self) -> float:
        """进度百分比"""
        if self.total_steps == 0:
            return 0.0
        return (self.current_step / self.total_steps) * 100

    @property
    def elapsed_seconds(self) -> float:
        """已用时间（秒）"""
        if self.start_time is None:
            return 0
        end = self.end_time or time.time()
        return end - self.start_time

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        return {
            "total_steps": self.total_steps,
            "current_step": self.current_step,
            "current_step_name": self.step_names[self.current_step] if self.current_step < len(self.step_names) else "end",
            "progress_percent": round(self.progress_percent, 1),
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "status": "completed" if self.end_time else "running",
        }


class StateTransitionValidator:
    """状态转换验证器"""

    # 定义合法的状态转换
    VALID_TRANSITIONS = {
        "start": ["planner"],
        "planner": ["architect", "end"],
        "architect": ["coder", "end"],
        "coder": ["tester", "end"],
        "tester": ["doc_writer", "coder", "end"],
        "doc_writer": ["end"],
        "end": [],
    }

    @classmethod
    def validate(cls, from_state: str, to_state: str) -> bool:
        """验证状态转换是否合法"""
        valid_next = cls.VALID_TRANSITIONS.get(from_state, [])
        return to_state in valid_next

    @classmethod
    def get_valid_next_states(cls, current_state: str) -> list[str]:
        """获取合法的下一状态列表"""
        return cls.VALID_TRANSITIONS.get(current_state, [])


class WorkflowError(Exception):
    """工作流错误"""
    pass


class WorkflowTimeoutError(WorkflowError):
    """工作流超时错误"""
    pass


class AgentWorkflow:
    """
    Agent 工作流（增强版）

    使用 LangGraph 编排多 Agent 协同

    特性：
    - 状态转换验证
    - 错误恢复机制
    - 超时控制
    - 进度追踪
    - 依赖注入支持（v2.0.0 新增）
    
    使用方式：
        # 方式1：使用默认 Agent（从容器自动获取）
        workflow = AgentWorkflow()
        
        # 方式2：注入自定义 Agent
        workflow = AgentWorkflow(agents={
            "planner": CustomPlannerAgent(),
            "architect": CustomArchitectAgent(),
        })
        
        # 方式3：使用自定义容器
        container = AgentContainer()
        container.register_agent("planner", PlannerAgent())
        workflow = AgentWorkflow(container=container)
    """

    # 默认超时配置（秒）
    DEFAULT_NODE_TIMEOUT = 300  # 5分钟
    DEFAULT_WORKFLOW_TIMEOUT = 1800  # 30分钟
    MAX_RETRY_COUNT = 3
    
    # 默认 Agent 配置（用于懒加载）
    DEFAULT_AGENTS = ["planner", "architect", "coder", "tester", "doc_writer"]

    def __init__(
        self,
        workflow_id: str | None = None,
        node_timeout: int = DEFAULT_NODE_TIMEOUT,
        workflow_timeout: int = DEFAULT_WORKFLOW_TIMEOUT,
        enable_recovery: bool = True,
        container: AgentContainer | None = None,
        agents: dict[str, Any] | None = None,
    ):
        """
        初始化工作流

        Args:
            workflow_id: 工作流 ID
            node_timeout: 单节点超时（秒）
            workflow_timeout: 整体超时（秒）
            enable_recovery: 是否启用错误恢复
            container: 依赖注入容器（可选，默认使用全局容器）
            agents: Agent 实例字典（可选，用于直接注入）
        """
        self.workflow_id = workflow_id or f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.graph: StateGraph | None = None
        self.compiled_graph = None

        # 超时配置
        self.node_timeout = node_timeout
        self.workflow_timeout = workflow_timeout
        self.enable_recovery = enable_recovery

        # 状态追踪
        self.status = WorkflowStatus.PENDING
        self.progress = WorkflowProgress()
        self.error_history: list[dict[str, Any]] = []

        # 依赖注入：使用容器管理 Agent
        self._container = container or get_agent_container()
        self._agents: dict[str, Any] = {}
        
        # 如果提供了 Agent 实例，直接注册到本地缓存
        if agents:
            for name, agent in agents.items():
                self._agents[name] = agent

        # 回调函数
        self._on_progress: Callable[[WorkflowProgress], None] | None = None
        self._on_error: Callable[[Exception, str], None] | None = None
        
        # 事件处理器（从 executor.py 迁移）
        self._event_handlers: dict[str, list[Callable]] = {}

        logger.info(
            "AgentWorkflow initialized",
            workflow_id=self.workflow_id,
            node_timeout=node_timeout,
            workflow_timeout=workflow_timeout,
            use_di=True,
        )
    
    # ===========================================
    # 事件处理器机制（从 executor.py 迁移）
    # ===========================================
    
    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """
        注册事件处理器
        
        Args:
            event_type: 事件类型（workflow_started, workflow_completed, workflow_failed, task_started, task_completed）
            handler: 处理函数（可以是同步或异步函数）
        
        示例:
            >>> workflow.register_event_handler("workflow_started", on_workflow_start)
            >>> workflow.register_event_handler("task_completed", on_task_done)
        """
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)
        logger.debug(f"Event handler registered: {event_type}")
    
    async def _emit_event(self, event_type: str, data: dict[str, Any]) -> None:
        """
        触发事件
        
        Args:
            event_type: 事件类型
            data: 事件数据
        """
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(data)
                else:
                    handler(data)
            except Exception as e:
                logger.error(
                    "Event handler failed",
                    event_type=event_type,
                    error=str(e),
                )

    def _get_agent(self, name: str) -> Any:
        """
        获取 Agent 实例（支持依赖注入）
        
        优先级：
        1. 本地缓存的 Agent 实例
        2. 容器中注册的 Agent
        3. 容器中的工厂函数（懒加载）
        
        Args:
            name: Agent 名称
            
        Returns:
            Agent 实例
        """
        # 1. 检查本地缓存
        if name in self._agents:
            return self._agents[name]
        
        # 2. 从容器获取
        try:
            agent = self._container.get_agent(name)
            self._agents[name] = agent  # 缓存到本地
            return agent
        except KeyError:
            logger.warning(
                "Agent not found in container, using default factory",
                agent_name=name,
            )
            # 3. 使用默认工厂创建（向后兼容）
            agent = self._create_default_agent(name)
            self._agents[name] = agent
            return agent

    def _create_default_agent(self, name: str) -> Any:
        """
        创建默认 Agent（向后兼容）
        
        当容器中没有注册 Agent 时，使用此方法创建默认实例。
        这确保了现有代码的向后兼容性。
        
        Args:
            name: Agent 名称
            
        Returns:
            Agent 实例
        """
        # 延迟导入以避免循环依赖
        from ..agents.architect import ArchitectAgent
        from ..agents.coder import CoderAgent
        from ..agents.doc_writer import DocWriterAgent
        from ..agents.planner import PlannerAgent
        from ..agents.tester import TesterAgent
        
        agent_factories = {
            "planner": PlannerAgent,
            "architect": ArchitectAgent,
            "coder": CoderAgent,
            "tester": TesterAgent,
            "doc_writer": DocWriterAgent,
        }
        
        if name not in agent_factories:
            raise ValueError(f"Unknown agent: {name}")
            
        logger.info(f"Creating default agent: {name}")
        return agent_factories[name]()
    
    @property
    def planner(self) -> Any:
        """获取 Planner Agent"""
        return self._get_agent("planner")
    
    @property
    def architect(self) -> Any:
        """获取 Architect Agent"""
        return self._get_agent("architect")
    
    @property
    def coder(self) -> Any:
        """获取 Coder Agent"""
        return self._get_agent("coder")
    
    @property
    def tester(self) -> Any:
        """获取 Tester Agent"""
        return self._get_agent("tester")
    
    @property
    def doc_writer(self) -> Any:
        """获取 DocWriter Agent"""
        return self._get_agent("doc_writer")

    def on_progress(self, callback: Callable[[WorkflowProgress], None]) -> None:
        """设置进度回调"""
        self._on_progress = callback

    def on_error(self, callback: Callable[[Exception, str], None]) -> None:
        """设置错误回调"""
        self._on_error = callback

    def _report_progress(self, step_name: str) -> None:
        """报告进度"""
        self.progress.advance(step_name)
        if self._on_progress:
            try:
                self._on_progress(self.progress)
            except Exception as e:
                logger.warning("Progress callback failed", error=str(e))

    def _record_error(self, error: Exception, node: str) -> None:
        """记录错误"""
        error_record = {
            "timestamp": datetime.now().isoformat(),
            "node": node,
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        self.error_history.append(error_record)
        logger.error(
            "Workflow error recorded",
            node=node,
            error=str(error),
            error_type=type(error).__name__,
        )
        if self._on_error:
            try:
                self._on_error(error, node)
            except Exception as e:
                logger.warning("Error callback failed", error=str(e))

    async def _execute_with_timeout(
        self,
        coro,
        timeout: int,
        node_name: str,
    ) -> Any:
        """带超时控制的执行"""
        try:
            return await asyncio.wait_for(coro, timeout=timeout)
        except TimeoutError:
            raise WorkflowTimeoutError(
                f"Node '{node_name}' timed out after {timeout} seconds"
            ) from None

    async def _execute_with_recovery(
        self,
        state: AgentState,
        node_func: Callable,
        node_name: str,
    ) -> dict[str, Any]:
        """带错误恢复的执行"""
        max_retries = self.MAX_RETRY_COUNT if self.enable_recovery else 1

        for attempt in range(max_retries):
            try:
                result = await self._execute_with_timeout(
                    node_func(state),
                    self.node_timeout,
                    node_name,
                )
                return result
            except WorkflowTimeoutError as e:
                self._record_error(e, node_name)
                if attempt < max_retries - 1:
                    logger.warning(
                        "Node timeout, retrying",
                        node=node_name,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                else:
                    state.error = str(e)
                    return state.dict()
            except Exception as e:
                self._record_error(e, node_name)
                if attempt < max_retries - 1:
                    logger.warning(
                        "Node failed, retrying",
                        node=node_name,
                        attempt=attempt + 1,
                        error=str(e),
                    )
                    await asyncio.sleep(2 ** attempt)
                else:
                    state.error = f"{node_name} failed: {str(e)}"
                    return state.dict()

        return state.dict()

    def build_graph(self) -> StateGraph:
        """
        构建工作流图

        Returns:
            StateGraph 实例
        """
        if not LANGGRAPH_AVAILABLE:
            logger.error("LangGraph not installed")
            raise ImportError("LangGraph is required. Install with: pip install langgraph")

        # 创建工作流图
        workflow = StateGraph(AgentState)

        # 添加节点
        workflow.add_node("start", self._start_node)
        workflow.add_node("planner", self._planner_node)
        workflow.add_node("architect", self._architect_node)
        workflow.add_node("coder", self._coder_node)
        workflow.add_node("tester", self._tester_node)
        workflow.add_node("doc_writer", self._doc_writer_node)
        workflow.add_node("end", self._end_node)

        # 添加边
        workflow.add_edge("start", "planner")
        workflow.add_edge("planner", "architect")
        workflow.add_edge("architect", "coder")
        workflow.add_edge("coder", "tester")

        # 条件边：测试通过后进入文档，否则返回编码
        workflow.add_conditional_edges(
            "tester",
            self._should_continue_to_doc,
            {
                "continue": "doc_writer",
                "retry": "coder",
                "__end__": "__end__",
            },
        )

        workflow.add_edge("doc_writer", "end")

        # 设置入口和结束
        workflow.set_entry_point("start")
        workflow.set_finish_point("end")

        self.graph = workflow

        logger.info("Workflow graph built")

        return workflow

    def compile(self) -> Any:
        """
        编译工作流

        Returns:
            编译后的工作流
        """
        if not self.graph:
            self.build_graph()

        self.compiled_graph = self.graph.compile()

        logger.info("Workflow compiled")

        return self.compiled_graph

    async def _start_node(self, state: AgentState) -> dict[str, Any]:
        """开始节点"""
        self.status = WorkflowStatus.RUNNING
        self.progress.start()

        logger.info(
            "Workflow started",
            task_id=state.task_id,
            task_title=state.task_title,
        )

        # 验证状态转换
        if not StateTransitionValidator.validate("start", "planner"):
            logger.warning("Invalid state transition: start -> planner")

        state.add_message("system", f"Starting task: {state.task_title}")
        state.current_step = "planner"

        self._report_progress("start")

        return state.dict()

    async def _planner_node(self, state: AgentState) -> dict[str, Any]:
        """规划器节点"""

        async def _execute():
            logger.info("Executing Planner Agent")

            from ..core.models import Task

            task = Task(
                id=state.task_id,
                title=state.task_title,
                description=state.task_description,
                input_data=state.input_data,
            )

            result = await self.planner.process_task(task)

            state.add_agent_result("planner", result.output_data)
            state.add_message(
                "assistant",
                f"Planning complete: {len(result.output_data.get('subtasks', []))} subtasks created",
            )

            state.current_step = "architect"
            return state.dict()

        self._report_progress("planner")
        return await self._execute_with_recovery(state, _execute, "planner")

    async def _architect_node(self, state: AgentState) -> dict[str, Any]:
        """架构师节点"""
        if state.has_error():
            return state.dict()

        async def _execute():
            logger.info("Executing Architect Agent")

            from ..core.models import Task

            task = Task(
                id=state.task_id,
                title="Architecture Design",
                input_data={
                    "requirements": state.task_description,
                    "plan": state.agent_results.get("planner", {}),
                },
            )

            result = await self.architect.process_task(task)

            state.add_agent_result("architect", result.output_data)
            state.add_message("assistant", "Architecture design complete")

            state.current_step = "coder"
            return state.dict()

        self._report_progress("architect")
        return await self._execute_with_recovery(state, _execute, "architect")

    async def _coder_node(self, state: AgentState) -> dict[str, Any]:
        """程序员节点"""
        if state.has_error():
            return state.dict()

        async def _execute():
            logger.info("Executing Coder Agent")

            from ..core.models import Task

            task = Task(
                id=state.task_id,
                title="Code Implementation",
                input_data={
                    "requirements": state.task_description,
                    "architecture": state.agent_results.get("architect", {}),
                },
            )

            result = await self.coder.process_task(task)

            state.add_agent_result("coder", result.output_data)
            state.add_message(
                "assistant",
                f"Coding complete: {result.output_data.get('files_created', 0)} files created",
            )

            state.current_step = "tester"
            return state.dict()

        self._report_progress("coder")
        return await self._execute_with_recovery(state, _execute, "coder")

    async def _tester_node(self, state: AgentState) -> dict[str, Any]:
        """测试员节点"""
        if state.has_error():
            return state.dict()

        async def _execute():
            logger.info("Executing Tester Agent")

            from ..core.models import Task

            task = Task(
                id=state.task_id,
                title="Testing",
                input_data={
                    "code_files": state.agent_results.get("coder", {}).get("code_files", []),
                    "requirements": state.task_description,
                },
            )

            result = await self.tester.process_task(task)

            state.add_agent_result("tester", result.output_data)

            passed = result.output_data.get("passed", 0)
            failed = result.output_data.get("failed", 0)

            state.add_message(
                "assistant",
                f"Testing complete: {passed} passed, {failed} failed",
            )

            state.current_step = "decision"
            return state.dict()

        self._report_progress("tester")
        return await self._execute_with_recovery(state, _execute, "tester")

    async def _doc_writer_node(self, state: AgentState) -> dict[str, Any]:
        """文档员节点"""
        if state.has_error():
            return state.dict()

        async def _execute():
            logger.info("Executing DocWriter Agent")

            from ..core.models import Task

            task = Task(
                id=state.task_id,
                title="Documentation",
                input_data={
                    "code_files": state.agent_results.get("coder", {}).get("code_files", []),
                    "test_results": state.agent_results.get("tester", {}),
                },
            )

            result = await self.doc_writer.process_task(task)

            state.add_agent_result("doc_writer", result.output_data)
            state.add_message("assistant", "Documentation complete")

            state.current_step = "end"
            return state.dict()

        self._report_progress("doc_writer")
        return await self._execute_with_recovery(state, _execute, "doc_writer")

    async def _end_node(self, state: AgentState) -> dict[str, Any]:
        """结束节点"""
        self.status = WorkflowStatus.COMPLETED if not state.has_error() else WorkflowStatus.FAILED
        self.progress.complete()

        logger.info(
            "Workflow completed",
            task_id=state.task_id,
            has_error=state.has_error(),
            status=self.status.value,
            elapsed_seconds=self.progress.elapsed_seconds,
        )

        state.add_message("system", "Workflow completed")
        state.metadata["workflow_progress"] = self.progress.to_dict()

        self._report_progress("end")

        return state.dict()

    def _should_continue_to_doc(self, state: AgentState) -> str:
        """判断是否进入文档节点"""
        if state.error:
            # 检查重试次数
            if state.retry_count >= self.MAX_RETRY_COUNT:
                logger.warning(
                    "Max retry count reached, ending workflow",
                    retry_count=state.retry_count,
                )
                return "__end__"
            state.retry_count += 1
            return "retry"

        test_result = state.agent_results.get("tester", {})
        failed = test_result.get("failed", 0) if isinstance(test_result, dict) else 0

        if failed > 0:
            if state.retry_count >= self.MAX_RETRY_COUNT:
                logger.warning(
                    "Max retry count reached for test failures",
                    retry_count=state.retry_count,
                    failed_tests=failed,
                )
                return "__end__"
            state.retry_count += 1
            return "retry"

        return "continue"

    async def run(
        self,
        task_id: str,
        task_title: str,
        task_description: str,
        input_data: dict | None = None,
    ) -> AgentState:
        """
        运行工作流

        Args:
            task_id: 任务 ID
            task_title: 任务标题
            task_description: 任务描述
            input_data: 输入数据

        Returns:
            最终状态
        """
        if not self.compiled_graph:
            self.compile()

        # 创建初始状态
        initial_state = AgentState(
            task_id=task_id,
            task_title=task_title,
            task_description=task_description,
            input_data=input_data or {},
        )

        logger.info(
            "Running workflow",
            task_id=task_id,
            task_title=task_title,
            workflow_timeout=self.workflow_timeout,
        )

        self.status = WorkflowStatus.RUNNING

        try:
            # 带整体超时控制的工作流执行
            final_state = await self._execute_with_timeout(
                self.compiled_graph.ainvoke(initial_state.dict()),
                self.workflow_timeout,
                "workflow",
            )

            return AgentState(**final_state)

        except WorkflowTimeoutError as e:
            self.status = WorkflowStatus.TIMEOUT
            self._record_error(e, "workflow")
            logger.error(
                "Workflow timed out",
                workflow_id=self.workflow_id,
                timeout=self.workflow_timeout,
            )
            # 返回错误状态
            initial_state.error = str(e)
            initial_state.metadata["workflow_progress"] = self.progress.to_dict()
            initial_state.metadata["error_history"] = self.error_history
            return initial_state

        except Exception as e:
            self.status = WorkflowStatus.FAILED
            self._record_error(e, "workflow")
            logger.error(
                "Workflow failed",
                workflow_id=self.workflow_id,
                error=str(e),
            )
            initial_state.error = str(e)
            initial_state.metadata["workflow_progress"] = self.progress.to_dict()
            initial_state.metadata["error_history"] = self.error_history
            return initial_state

    def get_status(self) -> dict[str, Any]:
        """获取工作流状态"""
        return {
            "workflow_id": self.workflow_id,
            "status": self.status.value,
            "progress": self.progress.to_dict(),
            "error_count": len(self.error_history),
            "errors": self.error_history[-5:] if self.error_history else [],
        }
    
    # ===========================================
    # 灵活工作流执行（从 executor.py 迁移并增强）
    # ===========================================
    
    async def execute_workflow_definition(
        self,
        workflow: WorkflowDefinition,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        执行工作流定义（支持复杂依赖关系）
        
        这是从 executor.py 迁移的核心功能，支持：
        - 灵活的任务依赖关系
        - 并行执行无依赖的任务
        - 事件通知机制
        - 错误处理和重试
        
        Args:
            workflow: 工作流定义
            context: 执行上下文
            
        Returns:
            执行结果字典
            
        示例:
            >>> workflow_def = WorkflowDefinition(
            ...     name="Custom Workflow",
            ...     tasks=[
            ...         WorkflowTask(agent_name="planner", task_description="Plan"),
            ...         WorkflowTask(agent_name="architect", task_description="Design", dependencies=["planner"]),
            ...         WorkflowTask(agent_name="coder", task_description="Code", dependencies=["architect"]),
            ...     ]
            ... )
            >>> result = await workflow.execute_workflow_definition(workflow_def)
        """
        logger.info(f"Starting workflow: {workflow.name}")
        await self._emit_event("workflow_started", {
            "workflow_name": workflow.name,
            "task_count": len(workflow.tasks),
        })

        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now()

        try:
            # 构建任务映射
            task_map = {task.agent_name: task for task in workflow.tasks}
            completed_tasks = set()
            results = {}

            # 执行任务（考虑依赖）
            while len(completed_tasks) < len(workflow.tasks):
                # 找到所有可以执行的任务（依赖已满足）
                ready_tasks = []
                for task in workflow.tasks:
                    if task.agent_name in completed_tasks:
                        continue
                    # 检查依赖是否满足
                    if all(dep in completed_tasks for dep in task.dependencies):
                        ready_tasks.append(task)

                if not ready_tasks:
                    # 检查是否有循环依赖
                    remaining = [t.agent_name for t in workflow.tasks if t.agent_name not in completed_tasks]
                    if remaining:
                        raise ValueError(f"Circular dependency detected: {remaining}")
                    break

                # 并发执行就绪任务
                tasks_to_run = [
                    self._execute_workflow_task(task, context, results)
                    for task in ready_tasks
                ]

                task_results = await asyncio.gather(*tasks_to_run, return_exceptions=True)

                # 处理结果
                for task, result in zip(ready_tasks, task_results, strict=False):
                    if isinstance(result, Exception):
                        task.status = TaskStatus.FAILED
                        task.error = str(result)
                        logger.error(f"Task failed: {task.agent_name} - {result}")

                        # 如果是关键任务失败，可以选择终止工作流
                        if task.retry_count == 0:
                            workflow.status = WorkflowStatus.FAILED
                            workflow.completed_at = datetime.now()
                            await self._emit_event("workflow_failed", {
                                "workflow_name": workflow.name,
                                "failed_task": task.agent_name,
                                "error": str(result),
                            })
                            return {"status": "failed", "error": str(result)}
                    else:
                        task.status = TaskStatus.COMPLETED
                        task.result = result
                        task.completed_at = datetime.now()
                        completed_tasks.add(task.agent_name)
                        results[task.agent_name] = result

                        logger.info(f"Task completed: {task.agent_name}")
                        await self._emit_event("task_completed", {
                            "agent_name": task.agent_name,
                            "result": result,
                        })

            # 所有任务完成
            workflow.status = WorkflowStatus.COMPLETED
            workflow.completed_at = datetime.now()

            await self._emit_event("workflow_completed", {
                "workflow_name": workflow.name,
                "results": results,
            })

            return {
                "status": "completed",
                "results": results,
                "workflow_name": workflow.name,
            }

        except Exception as e:
            workflow.status = WorkflowStatus.FAILED
            workflow.completed_at = datetime.now()
            logger.error(f"Workflow failed: {e}", exc_info=True)

            await self._emit_event("workflow_failed", {
                "workflow_name": workflow.name,
                "error": str(e),
            })

            return {"status": "failed", "error": str(e)}
    
    async def _execute_workflow_task(
        self,
        task: WorkflowTask,
        context: dict[str, Any] | None,
        previous_results: dict[str, Any],
    ) -> dict[str, Any]:
        """
        执行单个工作流任务
        
        Args:
            task: 工作流任务
            context: 执行上下文
            previous_results: 之前任务的结果
            
        Returns:
            任务执行结果
        """
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()

        logger.info(f"Executing task: {task.agent_name}")
        await self._emit_event("task_started", {
            "agent_name": task.agent_name,
            "description": task.task_description,
        })

        # 获取 Agent
        agent = self._get_agent(task.agent_name)

        # 准备任务数据
        task_input = {
            "description": task.task_description,
            "context": context,
            "previous_results": previous_results,
        }

        # 创建任务对象
        task_obj = Task(
            id=f"workflow_task_{task.agent_name}",
            title=task.agent_name,
            description=task.task_description,
            input_data=task_input,
        )

        # 执行 Agent（带超时控制）
        try:
            result = await asyncio.wait_for(
                agent.execute(task_obj),
                timeout=task.timeout_seconds,
            )
            return result
        except TimeoutError:
            raise TimeoutError(f"Task timeout: {task.agent_name} ({task.timeout_seconds}s)") from None
    
    def create_standard_workflow(self, workflow_name: str = "Standard Development Workflow") -> WorkflowDefinition:
        """
        创建标准研发工作流
        
        包含：Planner → Architect → Coder → Tester → DocWriter
        
        Args:
            workflow_name: 工作流名称
            
        Returns:
            工作流定义
            
        示例:
            >>> workflow_def = workflow.create_standard_workflow("My Project")
            >>> result = await workflow.execute_workflow_definition(workflow_def)
        """
        workflow = WorkflowDefinition(
            name=workflow_name,
            description="标准研发工作流",
        )

        # 添加标准任务
        workflow.tasks = [
            WorkflowTask(
                agent_name="planner",
                task_description="分析需求，制定任务计划",
                dependencies=[],
            ),
            WorkflowTask(
                agent_name="architect",
                task_description="设计系统架构",
                dependencies=["planner"],  # 依赖 planner
            ),
            WorkflowTask(
                agent_name="coder",
                task_description="实现代码",
                dependencies=["architect"],  # 依赖 architect
            ),
            WorkflowTask(
                agent_name="tester",
                task_description="编写和执行测试",
                dependencies=["coder"],  # 依赖 coder
            ),
            WorkflowTask(
                agent_name="doc_writer",
                task_description="编写文档",
                dependencies=["coder"],  # 依赖 coder（可以和 tester 并行）
            ),
        ]

        return workflow
    
    def get_workflow_status(self, workflow: WorkflowDefinition) -> dict[str, Any]:
        """
        获取工作流状态
        
        Args:
            workflow: 工作流定义
            
        Returns:
            工作流状态字典
        """
        return {
            "name": workflow.name,
            "status": workflow.status.value if workflow.status else "pending",
            "created_at": workflow.created_at.isoformat(),
            "started_at": workflow.started_at.isoformat() if workflow.started_at else None,
            "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
            "tasks": [
                {
                    "agent": task.agent_name,
                    "status": task.status.value,
                    "error": task.error,
                }
                for task in workflow.tasks
            ],
        }


def create_workflow(
    workflow_id: str | None = None,
    container: AgentContainer | None = None,
    agents: dict[str, Any] | None = None,
    **kwargs,
) -> AgentWorkflow:
    """
    创建工作流

    Args:
        workflow_id: 工作流 ID
        container: 依赖注入容器
        agents: Agent 实例字典（用于依赖注入）
        **kwargs: 其他配置参数

    Returns:
        AgentWorkflow 实例
        
    使用示例:
        # 基本用法
        workflow = create_workflow()
        
        # 使用自定义容器
        container = get_agent_container()
        container.register_agent("planner", CustomPlannerAgent())
        workflow = create_workflow(container=container)
        
        # 直接注入 Agent
        workflow = create_workflow(agents={
            "planner": PlannerAgent(),
            "architect": ArchitectAgent(),
        })
    """
    return AgentWorkflow(
        workflow_id=workflow_id,
        container=container,
        agents=agents,
        **kwargs,
    )


# ===========================================
# 向后兼容：提供 executor.py 的别名
# ===========================================

# 为了向后兼容，保留旧的类名和函数
Workflow = WorkflowDefinition  # 别名

# 提供类似 executor.py 的全局实例
_workflow_instance: AgentWorkflow | None = None


def get_workflow() -> AgentWorkflow:
    """
    获取全局工作流实例（向后兼容 executor.py）
    
    Returns:
        AgentWorkflow 实例
    """
    global _workflow_instance
    if _workflow_instance is None:
        _workflow_instance = AgentWorkflow()
    return _workflow_instance


async def init_workflow(agents: dict[str, Any]) -> AgentWorkflow:
    """
    初始化工作流（向后兼容 executor.py）
    
    Args:
        agents: Agent 实例字典
        
    Returns:
        AgentWorkflow 实例
    """
    workflow = get_workflow()
    for name, agent in agents.items():
        workflow._agents[name] = agent
    return workflow
