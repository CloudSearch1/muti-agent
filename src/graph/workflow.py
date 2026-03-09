"""
LangGraph 工作流编排（增强版）

职责：使用 LangGraph 编排多 Agent 协同工作流

增强功能：
- 状态转换验证
- 错误恢复机制
- 超时控制
- 进度追踪
- 并行执行支持
"""

import asyncio
import time
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Literal

import structlog

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    StateGraph = None
    END = "__end__"

from ..agents.architect import ArchitectAgent
from ..agents.coder import CoderAgent
from ..agents.doc_writer import DocWriterAgent
from ..agents.planner import PlannerAgent
from ..agents.tester import TesterAgent
from ..config.settings import get_settings
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


class WorkflowStatus(str, Enum):
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
    """

    # 默认超时配置（秒）
    DEFAULT_NODE_TIMEOUT = 300  # 5分钟
    DEFAULT_WORKFLOW_TIMEOUT = 1800  # 30分钟
    MAX_RETRY_COUNT = 3

    def __init__(
        self,
        workflow_id: str | None = None,
        node_timeout: int = DEFAULT_NODE_TIMEOUT,
        workflow_timeout: int = DEFAULT_WORKFLOW_TIMEOUT,
        enable_recovery: bool = True,
    ):
        """
        初始化工作流

        Args:
            workflow_id: 工作流 ID
            node_timeout: 单节点超时（秒）
            workflow_timeout: 整体超时（秒）
            enable_recovery: 是否启用错误恢复
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

        # 初始化 Agent
        get_settings()
        self.planner = PlannerAgent()
        self.architect = ArchitectAgent()
        self.coder = CoderAgent()
        self.tester = TesterAgent()
        self.doc_writer = DocWriterAgent()

        # 回调函数
        self._on_progress: Callable[[WorkflowProgress], None] | None = None
        self._on_error: Callable[[Exception, str], None] | None = None

        logger.info(
            "AgentWorkflow initialized",
            workflow_id=self.workflow_id,
            node_timeout=node_timeout,
            workflow_timeout=workflow_timeout,
        )

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
        except asyncio.TimeoutError:
            raise WorkflowTimeoutError(
                f"Node '{node_name}' timed out after {timeout} seconds"
            )

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


def create_workflow(
    workflow_id: str | None = None,
    **kwargs,
) -> AgentWorkflow:
    """
    创建工作流

    Args:
        workflow_id: 工作流 ID
        **kwargs: 其他配置参数

    Returns:
        AgentWorkflow 实例
    """
    return AgentWorkflow(workflow_id=workflow_id, **kwargs)