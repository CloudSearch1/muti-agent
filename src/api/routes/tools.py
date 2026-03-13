"""
工具系统 API 路由

提供工具列表、执行、进程管理等端点
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ...tools import get_registry, execute_tool
from ...tools.base import ToolStatus
from ...tools.builtin.exec import get_session_manager

router = APIRouter(prefix="/tools", tags=["工具系统"])

# ============================================================================
# 请求/响应模型
# ============================================================================


class ToolParameterSchema(BaseModel):
    """工具参数定义"""
    name: str
    type: str
    description: str
    required: bool = False
    default: Any = None


class ToolInfo(BaseModel):
    """工具信息"""
    name: str
    description: str
    category: str = "general"
    enabled: bool = True
    parameters: List[ToolParameterSchema] = []
    examples: List[Dict[str, Any]] = []


class ToolListResponse(BaseModel):
    """工具列表响应"""
    tools: List[ToolInfo]
    total: int
    timestamp: str


class ToolDetailResponse(BaseModel):
    """工具详情响应"""
    name: str
    description: str
    category: str
    enabled: bool
    parameters: List[ToolParameterSchema]
    examples: List[Dict[str, Any]]
    tool_schema: Dict[str, Any]


class ToolExecuteRequest(BaseModel):
    """工具执行请求"""
    tool_name: str
    params: Dict[str, Any] = {}
    agent_id: Optional[str] = None


class ToolExecuteResponse(BaseModel):
    """工具执行响应"""
    success: bool
    status: str
    data: Optional[Any] = None
    error: Optional[str] = None
    execution_time: float = 0.0
    timestamp: str


class ProcessInfo(BaseModel):
    """进程会话信息"""
    session_id: str
    status: str
    created_at: str
    last_activity: str
    command: Optional[str] = None


class ProcessListResponse(BaseModel):
    """进程列表响应"""
    processes: List[ProcessInfo]
    total: int


# ============================================================================
# 工具列表端点
# ============================================================================


@router.get("", response_model=ToolListResponse)
async def list_tools(
    category: Optional[str] = Query(None, description="按分类过滤"),
    enabled_only: bool = Query(True, description="是否只显示启用的工具"),
):
    """
    获取所有可用工具列表
    
    - **category**: 工具分类过滤（可选）
    - **enabled_only**: 是否只显示启用的工具
    """
    registry = get_registry()
    tools_data = registry.list_tools(enabled_only=enabled_only)
    
    # 过滤分类
    if category:
        tools_data = [t for t in tools_data if t.get("category", "general") == category]
    
    # 转换为响应格式
    tools = []
    for t in tools_data:
        params = []
        if hasattr(t, "PARAMETERS") and t["PARAMETERS"]:
            for p in t["PARAMETERS"]:
                params.append(ToolParameterSchema(
                    name=p.get("name", ""),
                    type=p.get("type", "string"),
                    description=p.get("description", ""),
                    required=p.get("required", False),
                    default=p.get("default"),
                ))
        
        tools.append(ToolInfo(
            name=t.get("name", t.get("NAME", "")),
            description=t.get("description", t.get("DESCRIPTION", "")),
            category=t.get("category", "general"),
            enabled=t.get("enabled", True),
            parameters=params,
            examples=t.get("examples", []),
        ))
    
    return ToolListResponse(
        tools=tools,
        total=len(tools),
        timestamp=datetime.now().isoformat(),
    )


@router.get("/name/{tool_name}", response_model=ToolDetailResponse)
async def get_tool_detail(tool_name: str):
    """
    获取指定工具的详细信息
    
    - **tool_name**: 工具名称
    """
    registry = get_registry()
    tool = registry.get(tool_name)
    
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具不存在：{tool_name}")
    
    # 获取参数定义
    params = []
    if hasattr(tool, "PARAMETERS") and tool.PARAMETERS:
        for p in tool.PARAMETERS:
            params.append(ToolParameterSchema(
                name=p.get("name", ""),
                type=p.get("type", "string"),
                description=p.get("description", ""),
                required=p.get("required", False),
                default=p.get("default"),
            ))
    
    return ToolDetailResponse(
        name=tool.NAME,
        description=tool.DESCRIPTION,
        category=getattr(tool, "CATEGORY", "general"),
        enabled=tool.enabled,
        parameters=params,
        examples=getattr(tool, "EXAMPLES", []),
        tool_schema=tool.to_dict() if hasattr(tool, "to_dict") else {},
    )


# ============================================================================
# 工具执行端点
# ============================================================================


@router.post("/execute", response_model=ToolExecuteResponse)
async def execute_tool_endpoint(request: ToolExecuteRequest):
    """
    执行指定工具
    
    - **tool_name**: 工具名称
    - **params**: 工具参数
    - **agent_id**: Agent ID（可选）
    """
    registry = get_registry()
    
    # 检查工具是否存在
    tool = registry.get(request.tool_name)
    if not tool:
        raise HTTPException(status_code=404, detail=f"工具不存在：{request.tool_name}")
    
    # 检查工具是否启用
    if not tool.enabled:
        raise HTTPException(status_code=400, detail=f"工具已禁用：{request.tool_name}")
    
    start_time = datetime.now()
    
    try:
        # 执行工具
        params = request.params.copy()
        if request.agent_id:
            params["agent_id"] = request.agent_id
        
        result = await registry.execute(request.tool_name, **params)
        
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        # 确定状态
        if hasattr(result, "status"):
            status = result.status.value if isinstance(result.status, ToolStatus) else str(result.status)
        else:
            status = "ok" if result.success else "error"
        
        return ToolExecuteResponse(
            success=result.success,
            status=status,
            data=result.data,
            error=result.error,
            execution_time=execution_time,
            timestamp=datetime.now().isoformat(),
        )
        
    except Exception as e:
        end_time = datetime.now()
        execution_time = (end_time - start_time).total_seconds()
        
        return ToolExecuteResponse(
            success=False,
            status="error",
            error=str(e),
            execution_time=execution_time,
            timestamp=datetime.now().isoformat(),
        )


# ============================================================================
# 进程管理端点
# ============================================================================


@router.get("/processes", response_model=ProcessListResponse)
async def list_processes():
    """获取所有后台进程会话"""
    try:
        session_manager = get_session_manager()
        sessions = session_manager.list_sessions()
        
        processes = []
        for session in sessions:
            processes.append(ProcessInfo(
                session_id=session.session_id,
                status=session.status,
                created_at=session.created_at.isoformat() if hasattr(session.created_at, "isoformat") else str(session.created_at),
                last_activity=session.last_activity.isoformat() if hasattr(session.last_activity, "isoformat") else str(session.last_activity),
                command=session.command,
            ))
        
        return ProcessListResponse(
            processes=processes,
            total=len(processes),
        )
    except Exception as e:
        return ProcessListResponse(processes=[], total=0)


@router.get("/processes/{session_id}")
async def get_process(session_id: str):
    """获取指定进程会话详情"""
    try:
        session_manager = get_session_manager()
        session = session_manager.get_session(session_id)
        
        if not session:
            raise HTTPException(status_code=404, detail=f"进程会话不存在：{session_id}")
        
        return {
            "session_id": session.session_id,
            "status": session.status,
            "created_at": session.created_at.isoformat() if hasattr(session.created_at, "isoformat") else str(session.created_at),
            "last_activity": session.last_activity.isoformat() if hasattr(session.last_activity, "isoformat") else str(session.last_activity),
            "command": session.command,
            "output": session.output if hasattr(session, "output") else [],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/processes/{session_id}/kill")
async def kill_process(session_id: str):
    """终止指定进程会话"""
    try:
        session_manager = get_session_manager()
        success = session_manager.kill_session(session_id)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"进程会话不存在：{session_id}")
        
        return {"success": True, "message": f"进程 {session_id} 已终止"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories")
async def list_categories():
    """获取所有工具分类"""
    registry = get_registry()
    tools_data = registry.list_tools(enabled_only=False)
    
    categories = set()
    for t in tools_data:
        cat = t.get("category", "general")
        categories.add(cat)
    
    return {
        "categories": list(categories),
        "total": len(categories),
    }
