"""
ReAct Architect Agent

基于 ReAct 模式的架构师 Agent。
"""

from typing import Any, Dict

from langchain.tools import BaseTool as LangChainTool
from langchain_core.language_models import BaseChatModel
import structlog

from ..core.models import AgentRole, Task
from ..react import ReActAgent, ReActConfig
from ..react.prompts import ARCHITECT_REACT_PROMPT
from ..react.tool_adapter import adapt_tools

logger = structlog.get_logger(__name__)


class ReactArchitectAgent(ReActAgent):
    """
    ReAct Architect Agent
    
    使用 ReAct 模式的架构师，擅长：
    - 分析系统需求和约束
    - 设计合理的架构方案
    - 评估技术选型
    - 制定技术规范
    
    特点：
    1. 系统思维：全局考虑系统设计
    2. 权衡分析：动态评估技术方案利弊
    3. 决策记录：完整的架构决策推理链
    
    使用示例：
        >>> from langchain_openai import ChatOpenAI
        >>> from src.agents.react_architect import ReactArchitectAgent
        >>> 
        >>> llm = ChatOpenAI(model="gpt-4")
        >>> architect = ReactArchitectAgent(llm=llm, tools=tools)
        >>> 
        >>> async with architect.lifecycle():
        ...     result = await architect.process_task(task)
    """
    
    ROLE = AgentRole.ARCHITECT
    
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
        初始化 ReAct Architect Agent
        
        Args:
            llm: LangChain 语言模型实例
            tools: 工具列表（已适配为 LangChain 格式）
            agent_id: Agent ID（可选，默认自动生成）
            role: Agent 角色（可选，默认使用 ARCHITECT）
            config: ReAct 配置（可选）
            **kwargs: 其他参数
        """
        import uuid
        
        # 设置默认值
        if agent_id is None:
            agent_id = f"react-architect-{uuid.uuid4().hex[:8]}"
        if role is None:
            role = self.ROLE
        
        # 设置默认配置
        if config is None:
            config = ReActConfig(
                max_iterations=12,
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
            prompt_template=ARCHITECT_REACT_PROMPT,
            **kwargs,
        )
        
        logger.info(
            "ReactArchitectAgent initialized",
            agent_id=self.agent.id,
            tool_count=len(tools),
        )
    
    async def think(self, context: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Architect 的思考过程
        
        Args:
            context: 上下文信息
            
        Returns:
            思考结果
        """
        context = context or {}
        return {
            "thought": "Analyzing architecture requirements",
            "context": context,
            "available_tools": [t.name for t in self.tools],
            "focus": ["system_design", "tech_evaluation", "risk_assessment"],
        }
    
    async def execute(self, task: Task) -> dict[str, Any]:
        """
        执行架构设计任务
        
        ReAct Architect 会自动：
        1. 分析系统需求和约束
        2. 搜索相关技术文档和最佳实践
        3. 设计系统架构
        4. 评估技术选型
        5. 输出架构设计文档
        
        Args:
            task: 架构设计任务
        
        Returns:
            {
                "output": "最终答案",
                "reasoning_chain": [...],
                "design_decisions": [...],  # 设计决策
                "tech_stack": [...],  # 技术栈选择
                "risks": [...],  # 识别的风险
            }
        """
        # 调用父类执行 ReAct 循环
        result = await super().execute(task)
        
        # 后处理：提取架构相关信息
        result["design_decisions"] = self._extract_design_decisions(result)
        result["tech_stack"] = self._extract_tech_stack(result)
        result["risks"] = self._extract_risks(result)
        
        return result
    
    def _extract_design_decisions(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """从推理链中提取设计决策"""
        decisions = []
        
        # 分析思考内容
        for step in result.get("reasoning_chain", []):
            thought = step.get("thought", "")
            # 如果思考中包含决策关键词
            decision_keywords = ["决定", "选择", "采用", "decide", "choose", "select", "recommend"]
            if any(keyword in thought.lower() for keyword in decision_keywords):
                decisions.append({
                    "thought": thought,
                    "action": step.get("action"),
                    "observation": step.get("observation"),
                })
        
        return decisions
    
    def _extract_tech_stack(self, result: dict[str, Any]) -> list[str]:
        """从推理链中提取技术栈信息"""
        tech_stack = []
        
        # 常见技术关键词
        tech_keywords = [
            "python", "java", "javascript", "typescript", "go", "rust",
            "react", "vue", "angular", "django", "flask", "fastapi",
            "postgresql", "mysql", "mongodb", "redis", "kafka",
            "docker", "kubernetes", "aws", "azure", "gcp",
        ]
        
        # 从最终答案和推理链中提取技术关键词
        output = result.get("output", "").lower()
        for tech in tech_keywords:
            if tech in output and tech not in tech_stack:
                tech_stack.append(tech)
        
        for step in result.get("reasoning_chain", []):
            observation = step.get("observation", "").lower()
            for tech in tech_keywords:
                if tech in observation and tech not in tech_stack:
                    tech_stack.append(tech)
        
        return tech_stack
    
    def _extract_risks(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        """从推理链中提取风险信息"""
        risks = []
        
        risk_keywords = ["风险", "问题", "挑战", "risk", "issue", "challenge", "concern"]
        
        for step in result.get("reasoning_chain", []):
            thought = step.get("thought", "")
            observation = step.get("observation", "")
            
            # 如果提到风险
            if any(keyword in thought.lower() or keyword in observation.lower() 
                   for keyword in risk_keywords):
                risks.append({
                    "thought": thought,
                    "observation": observation,
                })
        
        return risks


def create_react_architect_agent(
    llm: BaseChatModel,
    additional_tools: list[LangChainTool] | None = None,
    config: ReActConfig | None = None,
    **kwargs,
) -> ReactArchitectAgent:
    """
    创建 ReAct Architect Agent 的便捷函数
    
    Args:
        llm: LangChain 语言模型实例
        additional_tools: 额外的工具（可选）
        config: ReAct 配置（可选）
        **kwargs: 其他参数
    
    Returns:
        ReactArchitectAgent 实例
    """
    from ..tools import CodeTools, GitTools
    
    # 获取默认工具（直接使用工具实例）
    default_tools = [
        CodeTools(),
        GitTools(),
    ]
    
    # 尝试添加 WebSearchTool（如果可用）
    try:
        from ..tools import WebSearchTool
        default_tools.append(WebSearchTool())
    except ImportError:
        pass
    
    # 适配工具
    langchain_tools = adapt_tools(default_tools)
    
    # 添加额外工具
    if additional_tools:
        langchain_tools.extend(additional_tools)
    
    return ReactArchitectAgent(
        llm=llm,
        tools=langchain_tools,
        config=config,
        **kwargs,
    )
