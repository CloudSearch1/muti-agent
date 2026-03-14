"""
工具基类

职责：定义工具的通用接口和标准

工具系统架构:
┌─────────────────────────────────────────────────────────────┐
│                       ToolRegistry                           │
│  (注册、发现、执行工具)                                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                       BaseTool                               │
│  - 参数验证                                                  │
│  - 安全检查                                                  │
│  - 错误处理                                                  │
│  - 结果标准化                                                │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   FileTools              GitTools             TestingTools
   (文件操作)             (Git操作)            (测试工具)

使用示例:
    # 创建工具实例
    file_tool = FileTools(root_dir="/project")

    # 执行工具
    result = await file_tool(action="read", path="src/main.py")

    # 检查结果（新方式 - 推荐）
    if result.status == ToolStatus.OK:
        print(result.data["content"])
    else:
        print(f"Error: {result.error.message}")

    # 向后兼容方式
    if result.success:
        print(result.data["content"])
    else:
        print(f"Error: {result.error}")
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# ============================================================================
# 错误模型导入
# ============================================================================

from .errors import ErrorCode, StandardError, ToolError

__all__ = [
    "ToolParameter",
    "OutputField",
    "OutputSchema",
    "ToolStatus",
    "ToolResult",
    "ToolRuntimeInfo",
    "BaseTool",
    "ErrorCode",
    "StandardError",
    "ToolError",
]


# ============================================================================
# 工具状态枚举
# ============================================================================


class ToolStatus(str, Enum):
    """
    工具执行状态
    
    - OK: 成功完成
    - ACCEPTED: 已接受，异步处理中
    - RUNNING: 正在运行（长任务）
    - ERROR: 执行失败
    """
    
    OK = "ok"
    ACCEPTED = "accepted"
    RUNNING = "running"
    ERROR = "error"


# ============================================================================
# 运行时信息
# ============================================================================


class ToolRuntimeInfo(BaseModel):
    """
    工具运行时信息
    
    记录工具执行的运行时元数据，包括工具名称、动作、耗时等。
    """
    
    tool: str = Field(..., description="工具名称")
    action: str = Field(..., description="执行的动作")
    duration_ms: int = Field(..., description="执行耗时（毫秒）")
    session_id: Optional[str] = Field(default=None, description="长任务会话 ID")
    warnings: List[str] = Field(default_factory=list, description="警告信息列表")


# ============================================================================
# 工具参数定义
# ============================================================================


class ToolParameter(BaseModel):
    """工具参数定义"""

    name: str = Field(..., description="参数名称")
    description: str = Field(..., description="参数描述")
    type: str = Field(..., description="参数类型")
    required: bool = Field(default=False, description="是否必填")
    default: Any = Field(default=None, description="默认值")
    enum: list[Any] | None = Field(default=None, description="枚举值")


# ============================================================================
# 工具输出字段定义
# ============================================================================


class OutputField(BaseModel):
    """
    工具输出字段定义
    
    用于描述工具返回数据结构中的字段。
    
    示例:
        OutputField(
            name="content",
            description="文件内容",
            type="string"
        )
        
        OutputField(
            name="exit_code",
            description="退出码",
            type="integer"
        )
    """

    name: str = Field(..., description="字段名称")
    description: str = Field(..., description="字段描述")
    type: str = Field(..., description="字段类型")
    required: bool = Field(default=True, description="是否必填")
    enum: list[Any] | None = Field(default=None, description="枚举值")


class OutputSchema(BaseModel):
    """
    工具输出模式定义
    
    描述工具成功执行后的返回数据结构。
    支持嵌套对象和数组类型。
    
    示例:
        # 简单输出
        OutputSchema(
            description="文件内容",
            fields=[
                OutputField(name="content", type="string", description="文件内容"),
                OutputField(name="size", type="integer", description="文件大小"),
            ]
        )
        
        # 嵌套对象
        OutputSchema(
            description="进程信息",
            fields=[
                OutputField(name="session_id", type="string", description="会话ID"),
                OutputField(name="status", type="string", description="状态"),
            ],
            nested_schemas={
                "process_info": OutputSchema(...)
            }
        )
    """

    description: str = Field(default="", description="输出描述")
    fields: list[OutputField] = Field(default_factory=list, description="输出字段列表")
    nested_schemas: dict[str, "OutputSchema"] = Field(
        default_factory=dict, description="嵌套模式定义"
    )

    def to_dict(self) -> dict[str, Any]:
        """转换为字典"""
        result: dict[str, Any] = {
            "description": self.description,
            "type": "object",
            "properties": {},
            "required": [],
        }

        for field in self.fields:
            prop: dict[str, Any] = {
                "type": field.type,
                "description": field.description,
            }
            if field.enum:
                prop["enum"] = field.enum
            result["properties"][field.name] = prop
            
            if field.required:
                result["required"].append(field.name)

        # 处理嵌套模式
        for name, schema in self.nested_schemas.items():
            result["properties"][name] = schema.to_dict()
            if schema.fields and all(f.required for f in schema.fields):
                result["required"].append(name)

        if not result["required"]:
            del result["required"]

        return result


# ============================================================================
# 工具执行结果
# ============================================================================


class ToolResult(BaseModel):
    """
    工具执行结果
    
    标准化的工具返回结果，包含状态、数据、错误信息和元数据。
    支持向后兼容的 success 属性。
    
    示例:
        # 成功结果
        result = ToolResult.ok(data={"content": "file content"})
        
        # 错误结果
        result = ToolResult.error(
            code=ErrorCode.NOT_FOUND,
            message="文件不存在",
            details={"path": "/path/to/file"}
        )
        
        # 长任务运行中
        result = ToolResult.running(
            session_id="session-123",
            data={"progress": 50}
        )
    """
    
    # 新字段
    status: ToolStatus = Field(..., description="执行状态")
    data: Optional[Any] = Field(default=None, description="返回数据")
    error: Optional[StandardError] = Field(default=None, description="错误信息")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    runtime: Optional[ToolRuntimeInfo] = Field(default=None, description="运行时信息")
    
    # 向后兼容字段（deprecated，仅用于兼容旧代码）
    success: Optional[bool] = Field(default=None, description="[已弃用] 是否成功，请使用 status")
    
    def __init__(self, **data):
        """
        初始化工具结果
        
        自动处理向后兼容：
        - 如果提供了 success 但没有 status，根据 success 推断 status
        - 如果提供了 error 字符串，转换为 StandardError
        """
        # 向后兼容：success -> status
        if "success" in data and "status" not in data:
            success = data["success"]
            data["status"] = ToolStatus.OK if success else ToolStatus.ERROR
        
        # 向后兼容：error 字符串 -> StandardError
        if "error" in data and isinstance(data["error"], str):
            error_str = data["error"]
            data["error"] = StandardError(
                code=ErrorCode.INTERNAL_ERROR,
                message=error_str,
            )
        
        # 设置 success 属性以保持兼容
        if "status" in data:
            data["success"] = data["status"] == ToolStatus.OK
        
        super().__init__(**data)
    
    # ========================================================================
    # 便捷工厂方法
    # ========================================================================
    
    @classmethod
    def ok(cls, data: Optional[Any] = None, **metadata) -> "ToolResult":
        """
        创建成功结果
        
        Args:
            data: 返回数据
            **metadata: 元数据
            
        Returns:
            成功的 ToolResult
        """
        return cls(
            status=ToolStatus.OK,
            data=data,
            metadata=metadata,
        )
    
    @classmethod
    def accepted(cls, data: Optional[Any] = None, **metadata) -> "ToolResult":
        """
        创建已接受结果（异步处理）
        
        Args:
            data: 返回数据
            **metadata: 元数据
            
        Returns:
            已接受的 ToolResult
        """
        return cls(
            status=ToolStatus.ACCEPTED,
            data=data,
            metadata=metadata,
        )
    
    @classmethod
    def running(
        cls,
        session_id: str,
        data: Optional[Any] = None,
        **metadata,
    ) -> "ToolResult":
        """
        创建运行中结果（长任务）
        
        Args:
            session_id: 会话 ID
            data: 返回数据（如进度信息）
            **metadata: 元数据
            
        Returns:
            运行中的 ToolResult
        """
        return cls(
            status=ToolStatus.RUNNING,
            data=data,
            metadata={"session_id": session_id, **metadata},
        )
    
    @classmethod
    def error(
        cls,
        code: ErrorCode,
        message: str,
        retryable: bool = False,
        details: Optional[Dict[str, Any]] = None,
        hint: Optional[str] = None,
        **metadata,
    ) -> "ToolResult":
        """
        创建错误结果
        
        Args:
            code: 错误码
            message: 错误消息
            retryable: 是否可重试
            details: 错误详情
            hint: 解决建议
            **metadata: 元数据
            
        Returns:
            错误的 ToolResult
        """
        return cls(
            status=ToolStatus.ERROR,
            error=StandardError(
                code=code,
                message=message,
                retryable=retryable,
                details=details or {},
                hint=hint,
            ),
            metadata=metadata,
        )
    
    @classmethod
    def from_exception(cls, exc: Exception, **metadata) -> "ToolResult":
        """
        从异常创建错误结果
        
        Args:
            exc: 异常对象
            **metadata: 元数据
            
        Returns:
            错误的 ToolResult
        """
        if isinstance(exc, ToolError):
            return cls(
                status=ToolStatus.ERROR,
                error=exc.error,
                metadata=metadata,
            )
        
        # 普通异常转换为内部错误
        return cls.error(
            code=ErrorCode.INTERNAL_ERROR,
            message=str(exc),
            retryable=False,
            **metadata,
        )
    
    # ========================================================================
    # 辅助方法
    # ========================================================================
    
    def is_ok(self) -> bool:
        """检查是否成功"""
        return self.status == ToolStatus.OK
    
    def is_running(self) -> bool:
        """检查是否正在运行"""
        return self.status == ToolStatus.RUNNING
    
    def is_error(self) -> bool:
        """检查是否错误"""
        return self.status == ToolStatus.ERROR
    
    def get_session_id(self) -> Optional[str]:
        """获取会话 ID（长任务）"""
        return self.metadata.get("session_id")


class BaseTool(ABC):
    """
    工具抽象基类

    所有工具必须继承此类并实现核心方法
    """

    # 类变量：工具名称和描述
    NAME: str = None  # 必须在子类中定义
    DESCRIPTION: str = None
    SCHEMA_VERSION: str = "1.0.0"  # 工具 schema 版本，遵循语义化版本

    def __init__(self, **kwargs):
        """
        初始化工具

        Args:
            **kwargs: 工具配置参数
        """
        self.config = kwargs
        self.enabled = kwargs.get("enabled", True)

        self.logger = logger.bind(
            tool_name=self.NAME,
        )

        self.logger.debug("Tool initialized")

    @property
    @abstractmethod
    def parameters(self) -> list[ToolParameter]:
        """
        获取工具参数定义

        Returns:
            参数定义列表
        """
        pass

    @property
    def output_schema(self) -> OutputSchema | None:
        """
        获取工具输出模式定义

        描述工具成功执行后的返回数据结构。
        可选实现，默认返回 None。

        Returns:
            输出模式定义，如果未定义返回 None

        示例:
            @property
            def output_schema(self) -> OutputSchema:
                return OutputSchema(
                    description="文件内容",
                    fields=[
                        OutputField(name="content", type="string", description="文件内容"),
                        OutputField(name="size", type="integer", description="文件大小"),
                    ]
                )
        """
        return None

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        执行工具

        Args:
            **kwargs: 工具参数

        Returns:
            执行结果
        """
        pass

    def validate_params(self, **kwargs) -> tuple[bool, str | None]:
        """
        验证参数

        Args:
            **kwargs: 待验证的参数

        Returns:
            (是否有效，错误信息)
        """
        for param in self.parameters:
            # 检查必填参数
            if param.required and param.name not in kwargs:
                return False, f"Missing required parameter: {param.name}"

            # 检查参数类型
            if param.name in kwargs:
                value = kwargs[param.name]
                expected_type = param.type

                # 简单类型检查
                if expected_type == "string" and not isinstance(value, str):
                    return False, f"Parameter {param.name} must be a string"
                elif expected_type == "integer" and not isinstance(value, int):
                    return False, f"Parameter {param.name} must be an integer"
                elif expected_type == "boolean" and not isinstance(value, bool):
                    return False, f"Parameter {param.name} must be a boolean"
                elif expected_type == "array" and not isinstance(value, list):
                    return False, f"Parameter {param.name} must be an array"
                elif expected_type == "object" and not isinstance(value, dict):
                    return False, f"Parameter {param.name} must be an object"

                # 检查枚举值
                if param.enum and value not in param.enum:
                    return False, f"Parameter {param.name} must be one of {param.enum}"

        return True, None

    def to_dict(self) -> dict[str, Any]:
        """
        转换为字典 (用于 MCP 注册)

        Returns:
            工具信息字典
        """
        result = {
            "name": self.NAME,
            "description": self.DESCRIPTION,
            "schema_version": self.SCHEMA_VERSION,
            "parameters": [
                {
                    "name": p.name,
                    "description": p.description,
                    "type": p.type,
                    "required": p.required,
                    "default": p.default,
                    "enum": p.enum,
                }
                for p in self.parameters
            ],
            "enabled": self.enabled,
        }

        # 添加输出模式定义
        if self.output_schema:
            result["output_schema"] = self.output_schema.to_dict()

        return result

    async def __call__(self, **kwargs) -> ToolResult:
        """允许工具像函数一样调用"""
        if not self.enabled:
            return ToolResult(
                success=False,
                error=f"Tool {self.NAME} is disabled",
            )

        # 验证参数
        valid, error = self.validate_params(**kwargs)
        if not valid:
            return ToolResult(
                success=False,
                error=error,
            )

        # 执行工具
        try:
            result = await self.execute(**kwargs)
            return result
        except Exception as e:
            self.logger.error(
                "Tool execution failed",
                error=str(e),
            )
            return ToolResult(
                success=False,
                error=str(e),
            )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.NAME})"
