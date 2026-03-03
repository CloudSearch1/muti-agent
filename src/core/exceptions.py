"""
异常定义模块

职责: 定义项目专用异常类，统一错误处理
"""

from typing import Any


class IntelliTeamError(Exception):
    """IntelliTeam 基础异常"""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# ===========================================
# Agent 相关异常
# ===========================================

class AgentError(IntelliTeamError):
    """Agent 基础异常"""
    pass


class AgentNotFoundError(AgentError):
    """Agent 不存在"""

    def __init__(self, agent_name: str):
        super().__init__(
            message=f"Agent '{agent_name}' not found",
            code="AGENT_NOT_FOUND",
            details={"agent_name": agent_name},
        )


class AgentExecutionError(AgentError):
    """Agent 执行错误"""

    def __init__(self, agent_name: str, reason: str, details: dict | None = None):
        super().__init__(
            message=f"Agent '{agent_name}' execution failed: {reason}",
            code="AGENT_EXECUTION_ERROR",
            details={"agent_name": agent_name, "reason": reason, **(details or {})},
        )


class AgentTimeoutError(AgentError):
    """Agent 执行超时"""

    def __init__(self, agent_name: str, timeout_seconds: int):
        super().__init__(
            message=f"Agent '{agent_name}' execution timed out after {timeout_seconds}s",
            code="AGENT_TIMEOUT",
            details={"agent_name": agent_name, "timeout_seconds": timeout_seconds},
        )


# ===========================================
# 任务相关异常
# ===========================================

class TaskError(IntelliTeamError):
    """任务基础异常"""
    pass


class TaskNotFoundError(TaskError):
    """任务不存在"""

    def __init__(self, task_id: str):
        super().__init__(
            message=f"Task '{task_id}' not found",
            code="TASK_NOT_FOUND",
            details={"task_id": task_id},
        )


class TaskValidationError(TaskError):
    """任务验证失败"""

    def __init__(self, task_id: str, errors: list[str]):
        super().__init__(
            message=f"Task '{task_id}' validation failed",
            code="TASK_VALIDATION_ERROR",
            details={"task_id": task_id, "errors": errors},
        )


class TaskExecutionError(TaskError):
    """任务执行错误"""

    def __init__(self, task_id: str, reason: str):
        super().__init__(
            message=f"Task '{task_id}' execution failed: {reason}",
            code="TASK_EXECUTION_ERROR",
            details={"task_id": task_id, "reason": reason},
        )


# ===========================================
# 工作流相关异常
# ===========================================

class WorkflowError(IntelliTeamError):
    """工作流基础异常"""
    pass


class WorkflowNotFoundError(WorkflowError):
    """工作流不存在"""

    def __init__(self, workflow_id: str):
        super().__init__(
            message=f"Workflow '{workflow_id}' not found",
            code="WORKFLOW_NOT_FOUND",
            details={"workflow_id": workflow_id},
        )


class WorkflowTransitionError(WorkflowError):
    """工作流状态转换错误"""

    def __init__(self, workflow_id: str, from_state: str, to_state: str, reason: str):
        super().__init__(
            message=f"Workflow '{workflow_id}' cannot transition from '{from_state}' to '{to_state}': {reason}",
            code="WORKFLOW_TRANSITION_ERROR",
            details={
                "workflow_id": workflow_id,
                "from_state": from_state,
                "to_state": to_state,
                "reason": reason,
            },
        )


# ===========================================
# 知识库相关异常
# ===========================================

class KnowledgeError(IntelliTeamError):
    """知识库基础异常"""
    pass


class DocumentNotFoundError(KnowledgeError):
    """文档不存在"""

    def __init__(self, document_id: str):
        super().__init__(
            message=f"Document '{document_id}' not found",
            code="DOCUMENT_NOT_FOUND",
            details={"document_id": document_id},
        )


class EmbeddingError(KnowledgeError):
    """嵌入错误"""

    def __init__(self, text: str, reason: str):
        super().__init__(
            message=f"Failed to embed text: {reason}",
            code="EMBEDDING_ERROR",
            details={"text_preview": text[:100], "reason": reason},
        )


class RetrievalError(KnowledgeError):
    """检索错误"""

    def __init__(self, query: str, reason: str):
        super().__init__(
            message=f"Failed to retrieve for query: {reason}",
            code="RETRIEVAL_ERROR",
            details={"query": query, "reason": reason},
        )


# ===========================================
# 工具相关异常
# ===========================================

class ToolError(IntelliTeamError):
    """工具基础异常"""
    pass


class ToolNotFoundError(ToolError):
    """工具不存在"""

    def __init__(self, tool_name: str):
        super().__init__(
            message=f"Tool '{tool_name}' not found",
            code="TOOL_NOT_FOUND",
            details={"tool_name": tool_name},
        )


class ToolExecutionError(ToolError):
    """工具执行错误"""

    def __init__(self, tool_name: str, reason: str, details: dict | None = None):
        super().__init__(
            message=f"Tool '{tool_name}' execution failed: {reason}",
            code="TOOL_EXECUTION_ERROR",
            details={"tool_name": tool_name, "reason": reason, **(details or {})},
        )


# ===========================================
# 协作相关异常
# ===========================================

class CollaborationError(IntelliTeamError):
    """协作基础异常"""
    pass


class ConflictDetectedError(CollaborationError):
    """检测到冲突"""

    def __init__(self, conflict_id: str, description: str):
        super().__init__(
            message=f"Conflict detected: {description}",
            code="CONFLICT_DETECTED",
            details={"conflict_id": conflict_id, "description": description},
        )


class ArbitrationRequiredError(CollaborationError):
    """需要仲裁"""

    def __init__(self, conflict_id: str, agents: list[str]):
        super().__init__(
            message="Arbitration required to resolve conflict",
            code="ARBITRATION_REQUIRED",
            details={"conflict_id": conflict_id, "involved_agents": agents},
        )


# ===========================================
# 配置相关异常
# ===========================================

class ConfigurationError(IntelliTeamError):
    """配置错误"""

    def __init__(self, setting_name: str, reason: str):
        super().__init__(
            message=f"Configuration error for '{setting_name}': {reason}",
            code="CONFIGURATION_ERROR",
            details={"setting_name": setting_name, "reason": reason},
        )
