"""
工具基类

职责：定义工具的通用接口和标准
"""

from abc import ABC, abstractmethod
from typing import Any, Optional, Callable
from pydantic import BaseModel, Field
import structlog


logger = structlog.get_logger(__name__)


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str = Field(..., description="参数名称")
    description: str = Field(..., description="参数描述")
    type: str = Field(..., description="参数类型")
    required: bool = Field(default=False, description="是否必填")
    default: Any = Field(default=None, description="默认值")
    enum: Optional[list[Any]] = Field(default=None, description="枚举值")


class ToolResult(BaseModel):
    """工具执行结果"""
    success: bool = Field(..., description="是否成功")
    data: Optional[Any] = Field(default=None, description="返回数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")


class BaseTool(ABC):
    """
    工具抽象基类
    
    所有工具必须继承此类并实现核心方法
    """
    
    # 类变量：工具名称和描述
    NAME: str = None  # 必须在子类中定义
    DESCRIPTION: str = None
    
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
    
    def validate_params(self, **kwargs) -> tuple[bool, Optional[str]]:
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
        return {
            "name": self.NAME,
            "description": self.DESCRIPTION,
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
