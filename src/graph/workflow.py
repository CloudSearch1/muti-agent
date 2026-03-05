"""
LangGraph 工作流编排

职责：使用 LangGraph 编排多 Agent 协同工作流
"""

from datetime import datetime
from typing import Any, Literal

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


class AgentWorkflow:
    """
    Agent 工作流

    使用 LangGraph 编排多 Agent 协同
    """

    def __init__(self, workflow_id: str | None = None):
        """
        初始化工作流

        Args:
            workflow_id: 工作流 ID
        """
        self.workflow_id = workflow_id or f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.graph: StateGraph | None = None
        self.compiled_graph = None

        # 初始化 Agent
        get_settings()
        self.planner = PlannerAgent()
        self.architect = ArchitectAgent()
        self.coder = CoderAgent()
        self.tester = TesterAgent()
        self.doc_writer = DocWriterAgent()

        logger.info(
            "AgentWorkflow initialized",
            workflow_id=self.workflow_id,
        )

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
        logger.info(
            "Workflow started",
            task_id=state.task_id,
            task_title=state.task_title,
        )

        state.add_message("system", f"Starting task: {state.task_title}")
        state.current_step = "planner"

        return state.dict()

    async def _planner_node(self, state: AgentState) -> dict[str, Any]:
        """规划器节点"""
        logger.info("Executing Planner Agent")

        from ..core.models import Task

        task = Task(
            id=state.task_id,
            title=state.task_title,
            description=state.task_description,
            input_data=state.input_data,
        )

        try:
            result = await self.planner.process_task(task)

            state.add_agent_result("planner", result.output_data)
            state.add_message(
                "assistant",
                f"Planning complete: {len(result.output_data.get('subtasks', []))} subtasks created",
            )

        except Exception as e:
            logger.error("Planner failed", error=str(e))
            state.error = f"Planner failed: {str(e)}"

        state.current_step = "architect"

        return state.dict()

    async def _architect_node(self, state: AgentState) -> dict[str, Any]:
        """架构师节点"""
        if state.has_error():
            return state.dict()

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

        try:
            result = await self.architect.process_task(task)

            state.add_agent_result("architect", result.output_data)
            state.add_message("assistant", "Architecture design complete")

        except Exception as e:
            logger.error("Architect failed", error=str(e))
            state.error = f"Architect failed: {str(e)}"

        state.current_step = "coder"

        return state.dict()

    async def _coder_node(self, state: AgentState) -> dict[str, Any]:
        """程序员节点"""
        if state.has_error():
            return state.dict()

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

        try:
            result = await self.coder.process_task(task)

            state.add_agent_result("coder", result.output_data)
            state.add_message(
                "assistant",
                f"Coding complete: {result.output_data.get('files_created', 0)} files created",
            )

        except Exception as e:
            logger.error("Coder failed", error=str(e))
            state.error = f"Coder failed: {str(e)}"

        state.current_step = "tester"

        return state.dict()

    async def _tester_node(self, state: AgentState) -> dict[str, Any]:
        """测试员节点"""
        if state.has_error():
            return state.dict()

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

        try:
            result = await self.tester.process_task(task)

            state.add_agent_result("tester", result.output_data)

            passed = result.output_data.get("passed", 0)
            failed = result.output_data.get("failed", 0)

            state.add_message(
                "assistant",
                f"Testing complete: {passed} passed, {failed} failed",
            )

        except Exception as e:
            logger.error("Tester failed", error=str(e))
            state.error = f"Tester failed: {str(e)}"

        state.current_step = "decision"

        return state.dict()

    async def _doc_writer_node(self, state: AgentState) -> dict[str, Any]:
        """文档员节点"""
        if state.has_error():
            return state.dict()

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

        try:
            result = await self.doc_writer.process_task(task)

            state.add_agent_result("doc_writer", result.output_data)
            state.add_message("assistant", "Documentation complete")

        except Exception as e:
            logger.error("DocWriter failed", error=str(e))
            state.error = f"DocWriter failed: {str(e)}"

        state.current_step = "end"

        return state.dict()

    async def _end_node(self, state: AgentState) -> dict[str, Any]:
        """结束节点"""
        logger.info(
            "Workflow completed",
            task_id=state.task_id,
            has_error=state.has_error(),
        )

        state.add_message("system", "Workflow completed")

        return state.dict()

    def _should_continue_to_doc(self, state: AgentState) -> str:
        """判断是否进入文档节点"""
        if state.error:
            return "retry"

        test_result = state.agent_results.get("tester", {})
        failed = test_result.get("failed", 0) if isinstance(test_result, dict) else 0

        if failed > 0:
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
        )

        # 运行工作流
        final_state = await self.compiled_graph.ainvoke(initial_state.dict())

        return AgentState(**final_state)


def create_workflow(workflow_id: str | None = None) -> AgentWorkflow:
    """
    创建工作流

    Args:
        workflow_id: 工作流 ID

    Returns:
        AgentWorkflow 实例
    """
    return AgentWorkflow(workflow_id)
