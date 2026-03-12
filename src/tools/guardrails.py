"""
循环检测与护栏模块

职责：
1. 检测 agent 的循环行为模式
2. 提供三级告警：warning、critical、circuit_breaker
3. 支持 agent 级配置覆盖

架构：
┌─────────────────────────────────────────────────────────────┐
│                     LoopDetector                              │
│  (主控制器：记录调用、检测循环、触发信号)                      │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
  GenericRepeat      KnownPollNoProgress      PingPongDetector
  (通用重复检测)      (无进展轮询检测)         (乒乓消息检测)

使用示例:
    config = LoopDetectionConfig()
    detector = LoopDetector(config)
    
    # 记录调用
    detector.record_call(agent_id="agent-1", call=tool_call, result=tool_result)
    
    # 检查循环
    signal = detector.check(agent_id="agent-1")
    if signal:
        print(f"Loop detected: {signal.level} - {signal.reason}")
"""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from enum import Enum
from typing import Any, Optional

import structlog
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)


# ============================================================================
# 数据模型
# ============================================================================


class LoopLevel(str, Enum):
    """循环告警级别"""

    WARNING = "warning"
    CRITICAL = "critical"
    CIRCUIT_BREAKER = "circuit_breaker"


class LoopSignal(BaseModel):
    """循环信号 - 当检测到循环行为时产生"""

    level: LoopLevel = Field(..., description="告警级别")
    detector: str = Field(..., description="检测器名称")
    score: int = Field(..., ge=0, description="循环得分/重复次数")
    reason: str = Field(..., description="循环原因描述")
    snapshot_id: Optional[str] = Field(default=None, description="快照ID，用于调试")
    suggested_action: str = Field(
        default="continue", description="建议动作: continue | pause | stop"
    )


class DetectorConfig(BaseModel):
    """检测器开关配置"""

    generic_repeat: bool = Field(default=True, description="启用通用重复检测")
    known_poll_no_progress: bool = Field(default=True, description="启用无进展轮询检测")
    ping_pong: bool = Field(default=True, description="启用乒乓消息检测")


class LoopDetectionConfig(BaseModel):
    """循环检测配置"""

    enabled: bool = Field(default=True, description="是否启用循环检测")
    warning_threshold: int = Field(default=10, ge=1, description="警告阈值")
    critical_threshold: int = Field(default=20, ge=1, description="严重阈值")
    global_circuit_breaker_threshold: int = Field(
        default=50, ge=1, description="全局熔断阈值"
    )
    history_size: int = Field(default=30, ge=5, description="历史记录大小")
    detectors: DetectorConfig = Field(
        default_factory=DetectorConfig, description="检测器配置"
    )


class ToolCall(BaseModel):
    """工具调用记录"""

    tool_name: str = Field(..., description="工具名称")
    action: Optional[str] = Field(default=None, description="动作名称（多动作工具）")
    arguments: dict[str, Any] = Field(default_factory=dict, description="调用参数")
    timestamp: float = Field(default_factory=time.time, description="调用时间戳")

    @property
    def signature(self) -> str:
        """生成调用签名，用于重复检测"""
        if self.action:
            return f"{self.tool_name}.{self.action}"
        return self.tool_name

    def content_hash(self) -> str:
        """生成内容哈希，用于检测相同参数的重复调用"""
        content = f"{self.signature}:{sorted(self.arguments.items())}"
        return hashlib.md5(content.encode()).hexdigest()[:8]


class ToolResult(BaseModel):
    """工具调用结果"""

    success: bool = Field(..., description="是否成功")
    data: Optional[Any] = Field(default=None, description="返回数据")
    error: Optional[str] = Field(default=None, description="错误信息")
    metadata: dict[str, Any] = Field(default_factory=dict, description="元数据")

    def content_hash(self) -> str:
        """生成结果内容哈希，用于检测结果是否变化"""
        if self.data is None:
            return hashlib.md5(b"empty").hexdigest()[:8]
        content = str(sorted(self._flatten_data(self.data)))
        return hashlib.md5(content.encode()).hexdigest()[:8]

    def _flatten_data(self, data: Any, prefix: str = "") -> list[tuple[str, Any]]:
        """扁平化数据结构"""
        items = []
        if isinstance(data, dict):
            for k, v in data.items():
                items.extend(self._flatten_data(v, f"{prefix}.{k}" if prefix else k))
        elif isinstance(data, list):
            for i, v in enumerate(data):
                items.extend(self._flatten_data(v, f"{prefix}[{i}]"))
        else:
            items.append((prefix, data))
        return items


class CallRecord(BaseModel):
    """完整的调用记录（调用 + 结果）"""

    call: ToolCall = Field(..., description="工具调用")
    result: ToolResult = Field(..., description="调用结果")
    sequence: int = Field(default=0, description="序列号")


# ============================================================================
# 检测器基类
# ============================================================================


class LoopDetectorBase:
    """循环检测器基类"""

    DETECTOR_NAME: str = "base"

    def detect(
        self,
        history: list[CallRecord],
        config: LoopDetectionConfig,
    ) -> Optional[LoopSignal]:
        """
        检测循环行为

        Args:
            history: 调用历史记录
            config: 检测配置

        Returns:
            如果检测到循环，返回 LoopSignal；否则返回 None
        """
        raise NotImplementedError


# ============================================================================
# 检测器实现
# ============================================================================


class GenericRepeatDetector(LoopDetectorBase):
    """
    通用重复检测器

    检测相同工具/动作的重复执行。
    当同一个工具调用在历史记录中出现次数超过阈值时触发。
    """

    DETECTOR_NAME = "genericRepeat"

    def detect(
        self,
        history: list[CallRecord],
        config: LoopDetectionConfig,
    ) -> Optional[LoopSignal]:
        if not history:
            return None

        # 统计每个签名的出现次数
        signature_counts: dict[str, int] = defaultdict(int)
        signature_first_seq: dict[str, int] = {}

        for record in history:
            sig = record.call.signature
            signature_counts[sig] += 1
            if sig not in signature_first_seq:
                signature_first_seq[sig] = record.sequence

        # 找出重复次数最多的签名
        max_sig = max(signature_counts.keys(), key=lambda k: signature_counts[k])
        max_count = signature_counts[max_sig]

        if max_count >= config.critical_threshold:
            return LoopSignal(
                level=LoopLevel.CRITICAL,
                detector=self.DETECTOR_NAME,
                score=max_count,
                reason=f"Tool '{max_sig}' repeated {max_count} times (critical threshold: {config.critical_threshold})",
                suggested_action="stop",
            )

        if max_count >= config.warning_threshold:
            return LoopSignal(
                level=LoopLevel.WARNING,
                detector=self.DETECTOR_NAME,
                score=max_count,
                reason=f"Tool '{max_sig}' repeated {max_count} times (warning threshold: {config.warning_threshold})",
                suggested_action="pause",
            )

        return None


class KnownPollNoProgressDetector(LoopDetectorBase):
    """
    无进展轮询检测器

    检测轮询操作（如 process.poll）持续返回相同结果。
    这表明后台任务可能卡住或没有进展。
    """

    DETECTOR_NAME = "knownPollNoProgress"

    # 已知的轮询工具/动作
    POLL_SIGNATURES = {
        "process.poll",
        "process.status",
        "process.log",
        "session_status",
    }

    def detect(
        self,
        history: list[CallRecord],
        config: LoopDetectionConfig,
    ) -> Optional[LoopSignal]:
        if not history:
            return None

        # 筛选轮询调用
        poll_records = [
            r
            for r in history
            if r.call.signature in self.POLL_SIGNATURES
        ]

        if not poll_records:
            return None

        # 按签名分组，检查每组是否有进展
        for sig in set(r.call.signature for r in poll_records):
            sig_records = [r for r in poll_records if r.call.signature == sig]

            # 检查结果哈希是否相同
            result_hashes = [r.result.content_hash() for r in sig_records]

            # 计算连续相同结果的次数
            same_count = self._count_consecutive_same(result_hashes)

            if same_count >= config.warning_threshold:
                return LoopSignal(
                    level=LoopLevel.WARNING,
                    detector=self.DETECTOR_NAME,
                    score=same_count,
                    reason=f"Poll '{sig}' returned same result {same_count} times without progress",
                    suggested_action="pause",
                )

        return None

    def _count_consecutive_same(self, hashes: list[str]) -> int:
        """计算末尾连续相同哈希的数量"""
        if not hashes:
            return 0

        last_hash = hashes[-1]
        count = 0
        for h in reversed(hashes):
            if h == last_hash:
                count += 1
            else:
                break
        return count


class PingPongDetector(LoopDetectorBase):
    """
    乒乓消息检测器

    检测两个工具之间来回切换的模式，如 A -> B -> A -> B。
    这种模式通常表示 agent 陷入了两个工具之间的死循环。
    """

    DETECTOR_NAME = "pingPong"

    def detect(
        self,
        history: list[CallRecord],
        config: LoopDetectionConfig,
    ) -> Optional[LoopSignal]:
        if len(history) < 4:
            return None

        # 提取最近的签名序列
        signatures = [r.call.signature for r in history]

        # 检测乒乓模式
        ping_pong_count = self._count_ping_pong_patterns(signatures)

        if ping_pong_count >= config.critical_threshold:
            return LoopSignal(
                level=LoopLevel.CRITICAL,
                detector=self.DETECTOR_NAME,
                score=ping_pong_count,
                reason=f"Detected ping-pong pattern between tools, {ping_pong_count} switches detected",
                suggested_action="stop",
            )

        if ping_pong_count >= config.warning_threshold:
            return LoopSignal(
                level=LoopLevel.WARNING,
                detector=self.DETECTOR_NAME,
                score=ping_pong_count,
                reason=f"Detected potential ping-pong pattern, {ping_pong_count} switches detected",
                suggested_action="pause",
            )

        return None

    def _count_ping_pong_patterns(self, signatures: list[str]) -> int:
        """
        计算乒乓模式的出现次数

        例如: [A, B, A, B, A, B] 表示 3 次 A-B 切换
        """
        if len(signatures) < 4:
            return 0

        # 找出最近的历史中的乒乓模式
        count = 0
        i = len(signatures) - 1

        while i >= 3:
            # 检查 A -> B -> A -> B 模式
            if (
                signatures[i] == signatures[i - 2]
                and signatures[i - 1] == signatures[i - 3]
                and signatures[i] != signatures[i - 1]
            ):
                count += 1
                i -= 2  # 跳过这对
            else:
                break

        return count


# ============================================================================
# 主控制器
# ============================================================================


class LoopDetector:
    """
    循环检测主控制器

    负责管理每个 agent 的调用历史，并协调各个检测器进行循环检测。

    使用示例:
        config = LoopDetectionConfig(
            warning_threshold=5,
            critical_threshold=10,
        )
        detector = LoopDetector(config)

        # 记录调用
        detector.record_call(
            agent_id="agent-1",
            call=ToolCall(tool_name="read", arguments={"path": "/tmp/file"}),
            result=ToolResult(success=True, data="content"),
        )

        # 检查循环
        signal = detector.check("agent-1")
        if signal:
            handle_loop_signal(signal)

        # 重置（如开始新任务）
        detector.reset("agent-1")
    """

    def __init__(self, config: Optional[LoopDetectionConfig] = None):
        """
        初始化循环检测器

        Args:
            config: 检测配置，默认使用默认配置
        """
        self.config = config or LoopDetectionConfig()
        self._history: dict[str, list[CallRecord]] = defaultdict(list)
        self._sequence: dict[str, int] = defaultdict(int)
        self._global_call_count: int = 0

        # 初始化检测器
        self._detectors: list[LoopDetectorBase] = []

        if self.config.detectors.generic_repeat:
            self._detectors.append(GenericRepeatDetector())

        if self.config.detectors.known_poll_no_progress:
            self._detectors.append(KnownPollNoProgressDetector())

        if self.config.detectors.ping_pong:
            self._detectors.append(PingPongDetector())

        self._agent_configs: dict[str, LoopDetectionConfig] = {}

        logger.info(
            "LoopDetector initialized",
            enabled=self.config.enabled,
            warning_threshold=self.config.warning_threshold,
            critical_threshold=self.config.critical_threshold,
            detectors=[d.DETECTOR_NAME for d in self._detectors],
        )

    def set_agent_config(
        self, agent_id: str, config: LoopDetectionConfig
    ) -> None:
        """
        设置 agent 级配置覆盖

        Args:
            agent_id: Agent ID
            config: 该 agent 的检测配置
        """
        self._agent_configs[agent_id] = config
        logger.debug("Agent config set", agent_id=agent_id)

    def get_config(self, agent_id: str) -> LoopDetectionConfig:
        """
        获取 agent 的有效配置

        Args:
            agent_id: Agent ID

        Returns:
            该 agent 的配置（如果有覆盖）或全局配置
        """
        return self._agent_configs.get(agent_id, self.config)

    def record_call(
        self,
        agent_id: str,
        call: ToolCall,
        result: ToolResult,
    ) -> None:
        """
        记录工具调用

        Args:
            agent_id: Agent ID
            call: 工具调用
            result: 调用结果
        """
        if not self.config.enabled:
            return

        config = self.get_config(agent_id)

        # 创建记录
        record = CallRecord(
            call=call,
            result=result,
            sequence=self._sequence[agent_id],
        )
        self._sequence[agent_id] += 1
        self._global_call_count += 1

        # 添加到历史
        self._history[agent_id].append(record)

        # 限制历史大小
        if len(self._history[agent_id]) > config.history_size:
            self._history[agent_id] = self._history[agent_id][-config.history_size :]

        logger.debug(
            "Call recorded",
            agent_id=agent_id,
            tool=call.signature,
            sequence=record.sequence,
        )

    def check(self, agent_id: str) -> Optional[LoopSignal]:
        """
        检查是否有循环行为

        Args:
            agent_id: Agent ID

        Returns:
            如果检测到循环，返回 LoopSignal；否则返回 None
        """
        if not self.config.enabled:
            return None

        config = self.get_config(agent_id)
        history = self._history.get(agent_id, [])

        if not history:
            return None

        # 首先检查全局熔断器
        if self._global_call_count >= config.global_circuit_breaker_threshold:
            return LoopSignal(
                level=LoopLevel.CIRCUIT_BREAKER,
                detector="global_circuit_breaker",
                score=self._global_call_count,
                reason=f"Global call count ({self._global_call_count}) exceeded circuit breaker threshold ({config.global_circuit_breaker_threshold})",
                suggested_action="stop",
            )

        # 运行各个检测器
        signals = []
        for detector in self._detectors:
            signal = detector.detect(history, config)
            if signal:
                signals.append(signal)

        # 返回最严重的信号
        if signals:
            signals.sort(key=lambda s: self._level_priority(s.level), reverse=True)
            return signals[0]

        return None

    def _level_priority(self, level: LoopLevel) -> int:
        """获取告警级别优先级"""
        priorities = {
            LoopLevel.CIRCUIT_BREAKER: 3,
            LoopLevel.CRITICAL: 2,
            LoopLevel.WARNING: 1,
        }
        return priorities.get(level, 0)

    def reset(self, agent_id: str) -> None:
        """
        重置 agent 的历史

        Args:
            agent_id: Agent ID
        """
        self._history[agent_id] = []
        self._sequence[agent_id] = 0
        logger.debug("History reset", agent_id=agent_id)

    def reset_global(self) -> None:
        """重置全局状态"""
        self._history = defaultdict(list)
        self._sequence = defaultdict(int)
        self._global_call_count = 0
        logger.info("Global state reset")

    def get_history(self, agent_id: str) -> list[CallRecord]:
        """
        获取 agent 的调用历史

        Args:
            agent_id: Agent ID

        Returns:
            调用历史列表
        """
        return self._history.get(agent_id, [])

    def get_stats(self, agent_id: str) -> dict[str, Any]:
        """
        获取 agent 的统计信息

        Args:
            agent_id: Agent ID

        Returns:
            统计信息字典
        """
        history = self._history.get(agent_id, [])

        # 统计工具调用分布
        tool_counts: dict[str, int] = defaultdict(int)
        for record in history:
            tool_counts[record.call.signature] += 1

        return {
            "total_calls": len(history),
            "global_calls": self._global_call_count,
            "unique_tools": len(tool_counts),
            "tool_distribution": dict(tool_counts),
            "last_call": history[-1].call.signature if history else None,
        }


# ============================================================================
# 便捷函数
# ============================================================================


# 全局实例
_detector: Optional[LoopDetector] = None


def get_loop_detector() -> LoopDetector:
    """获取全局循环检测器实例"""
    global _detector
    if _detector is None:
        _detector = LoopDetector()
    return _detector


def setup_loop_detector(config: LoopDetectionConfig) -> LoopDetector:
    """设置全局循环检测器"""
    global _detector
    _detector = LoopDetector(config)
    return _detector
