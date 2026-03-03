"""
Agent 路由

提供 Agent 管理相关的 API 端点
"""

from typing import Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import structlog


logger = structlog.get_logger(__name__)


router = APIRouter()


# ===========================================
# 请求/响应模型
# ===========================================

class AgentResponse(BaseModel):
    """Agent 响应"""
    id: str
    name: str
    role: str
    state: str
    enabled: bool
    statistics: dict[str, Any]


# ===========================================
# 模拟数据存储 (临时)
# ===========================================

_agents_db: dict[str, dict] = {}


# ===========================================
# API 端点
# ===========================================

@router.get(
    "/",
    response_model=list[AgentResponse],
    summary="列出 Agent",
)
async def list_agents(
    role: str = Query(None, description="角色过滤"),
    enabled: bool = Query(None, description="启用状态过滤"),
):
    """获取 Agent 列表"""
    agents = list(_agents_db.values())
    
    # 角色过滤
    if role:
        agents = [a for a in agents if a["role"] == role]
    
    # 启用状态过滤
    if enabled is not None:
        agents = [a for a in agents if a["enabled"] == enabled]
    
    return [AgentResponse(**a) for a in agents]


@router.get(
    "/{agent_id}",
    response_model=AgentResponse,
    summary="获取 Agent 详情",
)
async def get_agent(agent_id: str):
    """获取 Agent 详细信息"""
    agent = _agents_db.get(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return AgentResponse(**agent)


@router.get(
    "/{agent_id}/stats",
    summary="获取 Agent 统计",
)
async def get_agent_stats(agent_id: str):
    """获取 Agent 统计信息"""
    agent = _agents_db.get(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return agent.get("statistics", {})
