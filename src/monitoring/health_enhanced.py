"""
增强健康检查模块

提供详细的系统健康状态检查
"""

import asyncio
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.database import get_database_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["健康检查"])


# ============ 健康检查模型 ============

class HealthCheck(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="整体状态 (ok/degraded/down)")
    timestamp: str = Field(..., description="检查时间")
    version: str = Field(..., description="应用版本")
    checks: dict[str, Any] = Field(..., description="各组件检查状态")
    uptime_seconds: float = Field(..., description="运行时间（秒）")


class ComponentHealth(BaseModel):
    """组件健康状态"""
    status: str  # ok, error, degraded
    message: str
    latency_ms: float = 0.0
    details: dict[str, Any] = Field(default_factory=dict)


# ============ 启动时间追踪 ============

_start_time = datetime.now()


def get_uptime() -> float:
    """获取运行时间（秒）"""
    return (datetime.now() - _start_time).total_seconds()


# ============ 健康检查函数 ============

async def check_database(db: AsyncSession) -> ComponentHealth:
    """检查数据库连接"""
    try:
        start = datetime.now()
        await db.execute(text("SELECT 1"))
        latency = (datetime.now() - start).total_seconds() * 1000

        # 获取连接池统计
        db_manager = get_database_manager()
        pool_stats = db_manager.get_pool_stats()

        return ComponentHealth(
            status="ok",
            message="数据库连接正常",
            latency_ms=latency,
            details={
                "pool_stats": pool_stats,
            },
        )
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return ComponentHealth(
            status="error",
            message=f"数据库连接失败：{str(e)}",
            latency_ms=0,
            details={"error": str(e)},
        )


async def check_llm() -> ComponentHealth:
    """检查 LLM 连接"""
    try:
        from ..llm.llm_provider import get_llm

        start = datetime.now()
        llm = get_llm()

        # 简单测试调用
        await llm.generate("health check", max_tokens=1)
        latency = (datetime.now() - start).total_seconds() * 1000

        return ComponentHealth(
            status="ok",
            message="LLM 连接正常",
            latency_ms=latency,
            details={
                "provider": llm.__class__.__name__,
            },
        )
    except Exception as e:
        logger.error(f"LLM health check failed: {e}")
        return ComponentHealth(
            status="error",
            message=f"LLM 连接失败：{str(e)}",
            latency_ms=0,
            details={"error": str(e)},
        )


async def check_cache() -> ComponentHealth:
    """检查缓存连接"""
    try:
        from ..llm.cache import get_llm_cache

        start = datetime.now()
        cache = get_llm_cache()
        stats = cache.get_stats()
        latency = (datetime.now() - start).total_seconds() * 1000

        return ComponentHealth(
            status="ok",
            message="缓存正常",
            latency_ms=latency,
            details=stats,
        )
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return ComponentHealth(
            status="error",
            message=f"缓存检查失败：{str(e)}",
            latency_ms=0,
            details={"error": str(e)},
        )


async def check_memory() -> ComponentHealth:
    """检查内存使用"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()

        memory_mb = memory_info.rss / 1024 / 1024
        memory_percent = process.memory_percent()

        status = "ok"
        if memory_percent > 90:
            status = "degraded"
        elif memory_percent > 80:
            status = "warning"

        return ComponentHealth(
            status=status,
            message=f"内存使用：{memory_mb:.2f} MB ({memory_percent:.1f}%)",
            latency_ms=0,
            details={
                "memory_mb": memory_mb,
                "memory_percent": memory_percent,
                "available_mb": psutil.virtual_memory().available / 1024 / 1024,
            },
        )
    except ImportError:
        return ComponentHealth(
            status="ok",
            message="psutil 未安装，无法检查内存",
            latency_ms=0,
            details={"note": "psutil not installed"},
        )
    except Exception as e:
        logger.error(f"Memory health check failed: {e}")
        return ComponentHealth(
            status="error",
            message=f"内存检查失败：{str(e)}",
            latency_ms=0,
            details={"error": str(e)},
        )


# ============ API 端点 ============

@router.get("", response_model=HealthCheck)
@router.get("/", response_model=HealthCheck)
async def health_check(db: AsyncSession = Depends(get_database_manager)):
    """
    增强健康检查

    检查所有系统组件的健康状态：
    - 数据库连接
    - LLM 连接
    - 缓存系统
    - 内存使用

    返回整体状态：
    - **ok**: 所有组件正常
    - **degraded**: 部分组件异常但不影响核心功能
    - **down**: 核心组件故障
    """
    # 并发执行所有检查
    checks = await asyncio.gather(
        check_database(db),
        check_llm(),
        check_cache(),
        check_memory(),
        return_exceptions=False,
    )

    # 构建检查结果
    check_results = {
        "database": checks[0].dict(),
        "llm": checks[1].dict(),
        "cache": checks[2].dict(),
        "memory": checks[3].dict(),
    }

    # 确定整体状态
    statuses = [check["status"] for check in check_results.values()]

    if all(s == "ok" for s in statuses):
        overall_status = "ok"
    elif any(s == "error" for s in statuses):
        # 检查是否是核心组件错误
        core_errors = check_results["database"]["status"] == "error"
        overall_status = "down" if core_errors else "degraded"
    else:
        overall_status = "degraded"

    # 如果状态为 down，返回 503
    if overall_status == "down":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": overall_status,
                "checks": check_results,
            },
        )

    return HealthCheck(
        status=overall_status,
        timestamp=datetime.now().isoformat(),
        version="2.0.0",
        checks=check_results,
        uptime_seconds=get_uptime(),
    )


@router.get("/ready")
async def readiness_check(db: AsyncSession = Depends(get_database_manager)):
    """
    就绪检查

    检查应用是否准备好接收流量
    """
    db_health = await check_database(db)

    if db_health.status == "ok":
        return {"status": "ready", "timestamp": datetime.now().isoformat()}
    else:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "reason": db_health.message},
        )


@router.get("/live")
async def liveness_check():
    """
    存活检查

    检查应用是否还在运行
    """
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": get_uptime(),
    }


@router.get("/metrics")
async def health_metrics(db: AsyncSession = Depends(get_database_manager)):
    """
    健康指标

    返回 Prometheus 格式的健康指标
    """
    checks = await asyncio.gather(
        check_database(db),
        check_llm(),
        check_cache(),
        check_memory(),
    )

    metrics = []

    # 数据库指标
    db_status = 1 if checks[0].status == "ok" else 0
    metrics.append(f"app_health_database_status {db_status}")
    metrics.append(f'app_health_database_latency_ms {checks[0].latency_ms:.2f}')

    # LLM 指标
    llm_status = 1 if checks[1].status == "ok" else 0
    metrics.append(f"app_health_llm_status {llm_status}")
    metrics.append(f'app_health_llm_latency_ms {checks[1].latency_ms:.2f}')

    # 缓存指标
    cache_status = 1 if checks[2].status == "ok" else 0
    metrics.append(f"app_health_cache_status {cache_status}")

    # 内存指标
    if "memory_percent" in checks[3].details:
        metrics.append(f'app_health_memory_percent {checks[3].details["memory_percent"]:.2f}')

    # 运行时间
    metrics.append(f'app_uptime_seconds {get_uptime():.0f}')

    return "\n".join(metrics) + "\n"
