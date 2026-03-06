"""
自动扩缩容

基于负载自动扩缩容工作节点
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ScaleAction(str, Enum):
    """扩缩容动作"""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NO_ACTION = "no_action"


@dataclass
class ScalingPolicy:
    """扩缩容策略"""
    min_instances: int = 1
    max_instances: int = 10
    target_cpu_usage: float = 70.0  # 目标 CPU 使用率
    target_memory_usage: float = 70.0  # 目标内存使用率
    scale_up_threshold: float = 80.0  # 扩容阈值
    scale_down_threshold: float = 40.0  # 缩容阈值
    cooldown_seconds: int = 300  # 冷却时间
    evaluation_seconds: int = 60  # 评估间隔


@dataclass
class Metrics:
    """指标"""
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    request_rate: float = 0.0
    error_rate: float = 0.0
    latency_p95: float = 0.0
    queue_length: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AutoScaler:
    """
    自动扩缩容
    
    功能:
    - 基于 CPU/内存使用率
    - 基于请求速率
    - 基于队列长度
    - 冷却时间
    - 预测性扩缩容
    """
    
    def __init__(
        self,
        policy: Optional[ScalingPolicy] = None,
        scale_callback: Optional[Callable] = None,
    ):
        self.policy = policy or ScalingPolicy()
        self.scale_callback = scale_callback
        
        self.current_instances = self.policy.min_instances
        self.last_scale_action: Optional[datetime] = None
        self.metrics_history: List[Metrics] = []
        self._running = False
        self._scaler_task: Optional[asyncio.Task] = None
        
        logger.info(f"AutoScaler initialized (min={self.policy.min_instances}, max={self.policy.max_instances})")
    
    async def start(self):
        """启动扩缩容"""
        self._running = True
        self._scaler_task = asyncio.create_task(self._scaling_loop())
        logger.info("AutoScaler started")
    
    async def stop(self):
        """停止扩缩容"""
        self._running = False
        
        if self._scaler_task:
            self._scaler_task.cancel()
            try:
                await self._scaler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("AutoScaler stopped")
    
    def record_metrics(self, metrics: Metrics):
        """记录指标"""
        self.metrics_history.append(metrics)
        
        # 保留最近 1 小时的指标（每分钟 1 个）
        if len(self.metrics_history) > 60:
            self.metrics_history = self.metrics_history[-60:]
    
    async def _scaling_loop(self):
        """扩缩容循环"""
        while self._running:
            try:
                # 评估是否需要扩缩容
                action = self._evaluate_scaling()
                
                if action != ScaleAction.NO_ACTION:
                    await self._execute_scaling(action)
                
                await asyncio.sleep(self.policy.evaluation_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scaling loop error: {e}")
                await asyncio.sleep(self.policy.evaluation_seconds)
    
    def _evaluate_scaling(self) -> ScaleAction:
        """评估扩缩容"""
        # 检查冷却时间
        if self.last_scale_action:
            cooldown = (datetime.utcnow() - self.last_scale_action).total_seconds()
            if cooldown < self.policy.cooldown_seconds:
                logger.debug(f"In cooldown period: {cooldown:.0f}s/{self.policy.cooldown_seconds}s")
                return ScaleAction.NO_ACTION
        
        if not self.metrics_history:
            return ScaleAction.NO_ACTION
        
        # 计算平均指标
        avg_cpu = sum(m.cpu_usage for m in self.metrics_history[-10:]) / min(len(self.metrics_history), 10)
        avg_memory = sum(m.memory_usage for m in self.metrics_history[-10:]) / min(len(self.metrics_history), 10)
        avg_queue = sum(m.queue_length for m in self.metrics_history[-10:]) / min(len(self.metrics_history), 10)
        
        logger.info(f"Metrics: CPU={avg_cpu:.1f}%, Memory={avg_memory:.1f}%, Queue={avg_queue:.1f}")
        
        # 扩容判断
        if (
            avg_cpu > self.policy.scale_up_threshold or
            avg_memory > self.policy.scale_up_threshold or
            avg_queue > 100
        ):
            if self.current_instances < self.policy.max_instances:
                logger.info(f"Scale up triggered (CPU={avg_cpu:.1f}%, Memory={avg_memory:.1f}%)")
                return ScaleAction.SCALE_UP
        
        # 缩容判断
        if (
            avg_cpu < self.policy.scale_down_threshold and
            avg_memory < self.policy.scale_down_threshold and
            avg_queue < 10
        ):
            if self.current_instances > self.policy.min_instances:
                logger.info(f"Scale down triggered (CPU={avg_cpu:.1f}%, Memory={avg_memory:.1f}%)")
                return ScaleAction.SCALE_DOWN
        
        return ScaleAction.NO_ACTION
    
    async def _execute_scaling(self, action: ScaleAction):
        """执行扩缩容"""
        if action == ScaleAction.SCALE_UP:
            self.current_instances += 1
            logger.info(f"Scaled up to {self.current_instances} instances")
            
        elif action == ScaleAction.SCALE_DOWN:
            self.current_instances -= 1
            logger.info(f"Scaled down to {self.current_instances} instances")
        
        self.last_scale_action = datetime.utcnow()
        
        # 调用回调
        if self.scale_callback:
            try:
                if asyncio.iscoroutinefunction(self.scale_callback):
                    await self.scale_callback(action, self.current_instances)
                else:
                    self.scale_callback(action, self.current_instances)
            except Exception as e:
                logger.error(f"Scale callback error: {e}")
    
    def get_status(self) -> Dict[str, any]:
        """获取状态"""
        return {
            "current_instances": self.current_instances,
            "min_instances": self.policy.min_instances,
            "max_instances": self.policy.max_instances,
            "last_scale_action": self.last_scale_action.isoformat() if self.last_scale_action else None,
            "metrics_history_size": len(self.metrics_history),
            "current_metrics": self.metrics_history[-1].__dict__ if self.metrics_history else {},
        }


# ============ 预测性扩缩容 ============

class PredictiveScaler(AutoScaler):
    """
    预测性扩缩容
    
    基于历史模式预测负载，提前扩缩容
    """
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.hourly_patterns: Dict[int, float] = {}  # 小时 -> 平均负载
    
    def _learn_patterns(self):
        """学习历史模式"""
        if len(self.metrics_history) < 60 * 24:  # 至少 24 小时数据
            return
        
        # 按小时聚合
        hourly_loads: Dict[int, List[float]] = {}
        
        for metrics in self.metrics_history:
            hour = metrics.timestamp.hour
            if hour not in hourly_loads:
                hourly_loads[hour] = []
            hourly_loads[hour].append(metrics.cpu_usage)
        
        # 计算平均
        self.hourly_patterns = {
            hour: sum(loads) / len(loads)
            for hour, loads in hourly_loads.items()
        }
    
    def _predict_load(self, hours_ahead: int = 1) -> float:
        """预测负载"""
        future_hour = (datetime.utcnow().hour + hours_ahead) % 24
        return self.hourly_patterns.get(future_hour, 50.0)
    
    async def _scaling_loop(self):
        """预测性扩缩容循环"""
        while self._running:
            try:
                # 学习模式
                self._learn_patterns()
                
                # 预测 1 小时后的负载
                predicted_load = self._predict_load(hours_ahead=1)
                
                # 基于预测提前扩缩容
                if predicted_load > self.policy.scale_up_threshold:
                    if self.current_instances < self.policy.max_instances:
                        logger.info(f"Predictive scale up (predicted load={predicted_load:.1f}%)")
                        await self._execute_scaling(ScaleAction.SCALE_UP)
                
                elif predicted_load < self.policy.scale_down_threshold:
                    if self.current_instances > self.policy.min_instances:
                        logger.info(f"Predictive scale down (predicted load={predicted_load:.1f}%)")
                        await self._execute_scaling(ScaleAction.SCALE_DOWN)
                
                await asyncio.sleep(self.policy.evaluation_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Predictive scaling error: {e}")
                await asyncio.sleep(self.policy.evaluation_seconds)


# ============ 全局扩缩容器 ============

_scaler: Optional[AutoScaler] = None


def get_auto_scaler() -> AutoScaler:
    """获取扩缩容器"""
    global _scaler
    if _scaler is None:
        _scaler = AutoScaler()
    return _scaler


async def init_auto_scaler(**kwargs) -> AutoScaler:
    """初始化扩缩容器"""
    global _scaler
    _scaler = AutoScaler(**kwargs)
    await _scaler.start()
    logger.info("AutoScaler initialized")
    return _scaler


async def close_auto_scaler():
    """关闭扩缩容器"""
    global _scaler
    if _scaler:
        await _scaler.stop()
        _scaler = None
