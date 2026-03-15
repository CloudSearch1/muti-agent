"""
ReAct Coder Agent

基于 ReAct 模式的代码工程师 Agent。
"""

from typing import Any, Dict

from langchain.tools import BaseTool as LangChainTool
from langchain_core.language_models import BaseChatModel
import structlog

from ..core.models import AgentRole, Blackboard, Task
from ..react import ReActAgent, ReActConfig
from ..react.prompts import CODER_REACT_PROMPT
from ..react.tool_adapter import adapt_tools

logger = structlog.get_logger(__name__)


class ReactCoderAgent(ReActAgent):
    """
    ReAct Coder Agent
    
    使用 ReAct 模式的代码工程师，擅长：
    - 理解复杂的编程需求
    - 自动搜索相关代码和文档
    - 编写高质量的代码实现
    - 自主调试和修复问题
    
    特点：
    1. 动态推理：根据任务进展自主决策下一步
    2. 工具驱动：主动使用工具获取信息和验证代码
    3. 完整推理链：记录整个编码决策过程
    
    使用示例：
        >>> from langchain_openai import ChatOpenAI
        >>> from src.tools import CodeTools, FileTools
        >>> from src.agents.react_coder import ReactCoderAgent
        >>> 
        >>> llm = ChatOpenAI(model="gpt-4")
        >>> tools = [CodeTools(), FileTools()]
        >>> langchain_tools = adapt_tools(tools)
        >>> 
        >>> coder = ReactCoderAgent(llm=llm, tools=langchain_tools)
        >>> 
        >>> async with coder.lifecycle():
        ...     result = await coder.process_task(task)
    """
    
    ROLE = AgentRole.CODER
    
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
        初始化 ReAct Coder Agent
        
        Args:
            llm: LangChain 语言模型实例
            tools: 工具列表（已适配为 LangChain 格式）
            agent_id: Agent ID（可选，默认自动生成）
            role: Agent 角色（可选，默认使用 CODER）
            config: ReAct 配置（可选）
            **kwargs: 其他参数
        """
        import uuid
        
        # 设置默认值
        if agent_id is None:
            agent_id = f"react-coder-{uuid.uuid4().hex[:8]}"
        if role is None:
            role = self.ROLE
        
        # 设置默认配置
        if config is None:
            config = ReActConfig(
                max_iterations=15,
                max_execution_time=300.0,
                handle_parsing_errors=True,
                verbose=False,
            )
        
        super().__init__(
            agent_id=agent_id,
            role=role,
            llm=llm,
            tools=tools,
            config=config,
            prompt_template=CODER_REACT_PROMPT,
            **kwargs,
        )
        
        logger.info(
            "ReactCoderAgent initialized",
            agent_id=agent_id,
            tool_count=len(tools),
        )
    
    async def think(self, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Coder 的思考过程
        
        Args:
            context: 上下文信息
            
        Returns:
            思考结果
        """
        context = context or {}
        return {
            "thought": "Analyzing coding requirements",
            "context": context,
            "available_tools": [t.name for t in self.tools],
            "focus": ["code_search", "code_write", "test_run"],
        }
    
    async def execute(self, task: Task) -> dict[str, Any]:
        """
        执行编码任务
        
        ReAct Coder 会自动：
        1. 分析需求并制定编码计划
        2. 搜索相关代码和文档
        3. 编写代码实现
        4. 测试和验证代码
        5. 修复发现的问题
        
        Args:
            task: 编码任务
        
        Returns:
            {
                "output": "最终答案",
                "reasoning_chain": [...],
                "code_changes": [...],  # 代码变更记录
                "test_results": [...],  # 测试结果
            }
        """
        # 调用父类执行 ReAct 循环
        result = await super().execute(task)
        
        # 后处理：提取代码变更信息
        result["code_changes"] = self._extract_code_changes(result)
        result["test_results"] = self._extract_test_results(result)
        
        return result
    
    def _extract_code_changes(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """
        从推理链中提取代码变更信息
        
        Args:
            result: 执行结果
        
        Returns:
            代码变更列表
        """
        code_changes = []
        
        # 定义代码相关工具的动作名称模式
        code_action_patterns = [
            "write_code", "edit_code", "apply_patch",
            "write_file", "edit_file", "create_file",
            "write", "edit",
        ]
        
        for step in result.get("reasoning_chain", []):
            action = step.get("action", "")
            # 检查动作是否匹配代码相关模式
            if any(pattern in action.lower() for pattern in code_action_patterns):
                code_changes.append({
                    "action": action,
                    "input": step.get("action_input"),
                    "observation": step.get("observation"),
                })
        
        return code_changes
    
    def _extract_test_results(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """
        从推理链中提取测试结果
        
        Args:
            result: 执行结果
        
        Returns:
            测试结果列表
        """
        test_results = []
        
        # 定义测试相关工具的动作名称模式
        test_action_patterns = [
            "run_test", "run_unit_test", "run_integration_test",
            "test", "pytest", "unittest",
        ]
        
        for step in result.get("reasoning_chain", []):
            action = step.get("action", "")
            # 检查动作是否匹配测试相关模式
            if any(pattern in action.lower() for pattern in test_action_patterns):
                test_results.append({
                    "action": action,
                    "observation": step.get("observation"),
                })
        
        return test_results


# ============================================
# 工厂函数
# ============================================

def create_react_coder_agent(
    llm: BaseChatModel,
    additional_tools: list[LangChainTool] | None = None,
    config: ReActConfig | None = None,
    **kwargs,
) -> ReactCoderAgent:
    """
    创建 ReAct Coder Agent 的便捷函数
    
    Args:
        llm: LangChain 语言模型实例
        additional_tools: 额外的工具（可选）
        config: ReAct 配置（可选）
        **kwargs: 其他参数
    
    Returns:
        ReactCoderAgent 实例
    
    Example:
        >>> from langchain_openai import ChatOpenAI
        >>> 
        >>> llm = ChatOpenAI(model="gpt-4")
        >>> coder = create_react_coder_agent(llm)
    """
    from ..tools import CodeTools, FileTools, GitTools
    
    # 获取默认工具（直接使用工具实例）
    default_tools = [
        CodeTools(),
        FileTools(),
        GitTools(),
    ]
    
    # 适配工具
    langchain_tools = adapt_tools(default_tools)
    
    # 添加额外工具
    if additional_tools:
        langchain_tools.extend(additional_tools)
    
    return ReactCoderAgent(
        llm=llm,
        tools=langchain_tools,
        config=config,
        **kwargs,
    )
