"""
ReAct Tester Agent

基于 ReAct 模式的测试工程师 Agent。
"""

from typing import Any, Dict

from langchain.tools import BaseTool as LangChainTool
from langchain_core.language_models import BaseChatModel
import structlog

from ..core.models import AgentRole, Task
from ..react import ReActAgent, ReActConfig
from ..react.prompts import TESTER_REACT_PROMPT
from ..react.tool_adapter import adapt_tools

logger = structlog.get_logger(__name__)


class ReactTesterAgent(ReActAgent):
    """
    ReAct Tester Agent
    
    使用 ReAct 模式的测试工程师，擅长：
    - 分析代码并识别测试场景
    - 自动生成测试用例
    - 执行测试并分析结果
    - 发现和报告 Bug
    
    特点：
    1. 自主探索：动态决定测试策略
    2. 全面覆盖：自动识别边界条件
    3. 详细记录：完整的测试推理过程
    
    使用示例：
        >>> from langchain_openai import ChatOpenAI
        >>> from src.agents.react_tester import ReactTesterAgent
        >>> 
        >>> llm = ChatOpenAI(model="gpt-4")
        >>> tester = ReactTesterAgent(llm=llm, tools=tools)
        >>> 
        >>> async with tester.lifecycle():
        ...     result = await tester.process_task(task)
    """
    
    ROLE = AgentRole.TESTER
    
    def __init__(
        self,
        llm: BaseChatModel,
        tools: list[LangChainTool],
        agent_id: str | None = None,
        role: AgentRole | None = None,
        config: ReActConfig | None = None,
        **kwargs,
    ):
        """
        初始化 ReAct Tester Agent
        
        Args:
            llm: LangChain 语言模型实例
            tools: 工具列表（已适配为 LangChain 格式）
            agent_id: Agent ID（可选，默认自动生成）
            role: Agent 角色（可选，默认使用 TESTER）
            config: ReAct 配置（可选）
            **kwargs: 其他参数
        """
        import uuid
        
        # 设置默认值
        if agent_id is None:
            agent_id = f"react-tester-{uuid.uuid4().hex[:8]}"
        if role is None:
            role = self.ROLE
        
        # 设置默认配置
        if config is None:
            config = ReActConfig(
                max_iterations=12,
                max_execution_time=240.0,
                handle_parsing_errors=True,
                verbose=False,
            )
        
        super().__init__(
            agent_id=agent_id,
            role=role,
            llm=llm,
            tools=tools,
            config=config,
            prompt_template=TESTER_REACT_PROMPT,
            **kwargs,
        )
        
        logger.info(
            "ReactTesterAgent initialized",
            agent_id=self.agent.id,
            tool_count=len(tools),
        )
    
    async def think(self, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Tester 的思考过程
        
        Args:
            context: 上下文信息
            
        Returns:
            思考结果
        """
        context = context or {}
        return {
            "thought": "Analyzing test requirements",
            "context": context,
            "available_tools": [t.name for t in self.tools],
            "focus": ["code_analysis", "test_generation", "test_execution"],
        }
    
    async def execute(self, task: Task) -> dict[str, Any]:
        """
        执行测试任务
        
        ReAct Tester 会自动：
        1. 分析代码和需求
        2. 识别测试场景
        3. 生成测试用例
        4. 执行测试
        5. 分析结果并报告问题
        
        Args:
            task: 测试任务
        
        Returns:
            {
                "output": "最终答案",
                "reasoning_chain": [...],
                "test_cases": [...],  # 测试用例
                "bugs_found": [...],  # 发现的 Bug
                "coverage": {...},  # 测试覆盖率
            }
        """
        # 调用父类执行 ReAct 循环
        result = await super().execute(task)
        
        # 后处理：提取测试相关信息
        result["test_cases"] = self._extract_test_cases(result)
        result["bugs_found"] = self._extract_bugs(result)
        result["coverage"] = self._extract_coverage(result)
        
        return result
    
    def _extract_test_cases(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """从推理链中提取测试用例"""
        test_cases = []
        
        # 定义测试用例生成相关的动作模式
        test_gen_patterns = [
            "generate_test_case", "create_test", "write_test",
            "create_test_case", "generate_test",
        ]
        
        for step in result.get("reasoning_chain", []):
            action = step.get("action", "")
            if any(pattern in action.lower() for pattern in test_gen_patterns):
                test_cases.append({
                    "action": action,
                    "input": step.get("action_input"),
                    "observation": step.get("observation"),
                })
        
        return test_cases
    
    def _extract_bugs(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """从推理链中提取 Bug 信息"""
        bugs = []
        
        for step in result.get("reasoning_chain", []):
            observation = step.get("observation", "")
            # 检测错误或失败的关键词
            error_keywords = ["error", "fail", "exception", "traceback", "assertion"]
            if any(keyword in observation.lower() for keyword in error_keywords):
                bugs.append({
                    "action": step.get("action"),
                    "observation": observation,
                })
        
        return bugs
    
    def _extract_coverage(self, result: dict[str, Any]) -> dict[str, Any]:
        """从推理链中提取测试覆盖率信息"""
        coverage = {}
        
        # 定义覆盖率检查相关的动作模式
        coverage_patterns = ["run_test", "check_coverage", "coverage", "pytest"]
        
        for step in result.get("reasoning_chain", []):
            action = step.get("action", "")
            if any(pattern in action.lower() for pattern in coverage_patterns):
                observation = step.get("observation", "")
                # 尝试提取覆盖率数字
                if "%" in observation:
                    # 简单提取覆盖率信息
                    coverage["found"] = True
                    coverage["raw_observation"] = observation
                    break
        
        return coverage


def create_react_tester_agent(
    llm: BaseChatModel,
    additional_tools: list[LangChainTool] | None = None,
    config: ReActConfig | None = None,
    **kwargs,
) -> ReactTesterAgent:
    """
    创建 ReAct Tester Agent 的便捷函数
    
    Args:
        llm: LangChain 语言模型实例
        additional_tools: 额外的工具（可选）
        config: ReAct 配置（可选）
        **kwargs: 其他参数
    
    Returns:
        ReactTesterAgent 实例
    """
    from ..tools import CodeTools, TestingTools
    
    # 获取默认工具（直接使用工具实例）
    default_tools = [
        CodeTools(),
        TestingTools(),
    ]
    
    # 适配工具
    langchain_tools = adapt_tools(default_tools)
    
    # 添加额外工具
    if additional_tools:
        langchain_tools.extend(additional_tools)
    
    return ReactTesterAgent(
        llm=llm,
        tools=langchain_tools,
        config=config,
        **kwargs,
    )
