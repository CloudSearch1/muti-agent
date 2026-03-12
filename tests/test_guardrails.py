"""
循环检测模块单元测试

测试覆盖：
- LoopDetectionConfig 配置验证
- GenericRepeatDetector 通用重复检测
- KnownPollNoProgressDetector 无进展轮询检测
- PingPongDetector 乒乓消息检测
- LoopDetector 主控制器集成测试
"""

import pytest

from src.tools.guardrails import (
    CallRecord,
    DetectorConfig,
    GenericRepeatDetector,
    KnownPollNoProgressDetector,
    LoopDetectionConfig,
    LoopDetector,
    LoopLevel,
    LoopSignal,
    PingPongDetector,
    ToolCall,
    ToolResult,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def default_config() -> LoopDetectionConfig:
    """默认配置"""
    return LoopDetectionConfig()


@pytest.fixture
def strict_config() -> LoopDetectionConfig:
    """严格配置（低阈值）"""
    return LoopDetectionConfig(
        warning_threshold=3,
        critical_threshold=5,
        global_circuit_breaker_threshold=10,
    )


@pytest.fixture
def disabled_config() -> LoopDetectionConfig:
    """禁用配置"""
    return LoopDetectionConfig(
        enabled=False,
        warning_threshold=1,
        critical_threshold=2,
    )


# ============================================================================
# 配置模型测试
# ============================================================================


class TestLoopDetectionConfig:
    """测试 LoopDetectionConfig"""

    def test_default_values(self):
        """测试默认值"""
        config = LoopDetectionConfig()

        assert config.enabled is True
        assert config.warning_threshold == 10
        assert config.critical_threshold == 20
        assert config.global_circuit_breaker_threshold == 50
        assert config.history_size == 30
        assert config.detectors.generic_repeat is True
        assert config.detectors.known_poll_no_progress is True
        assert config.detectors.ping_pong is True

    def test_custom_values(self):
        """测试自定义值"""
        config = LoopDetectionConfig(
            enabled=False,
            warning_threshold=5,
            critical_threshold=10,
            global_circuit_breaker_threshold=20,
            history_size=15,
            detectors=DetectorConfig(
                generic_repeat=True,
                known_poll_no_progress=False,
                ping_pong=True,
            ),
        )

        assert config.enabled is False
        assert config.warning_threshold == 5
        assert config.critical_threshold == 10
        assert config.global_circuit_breaker_threshold == 20
        assert config.history_size == 15
        assert config.detectors.known_poll_no_progress is False

    def test_threshold_validation(self):
        """测试阈值验证"""
        # 有效的阈值
        config = LoopDetectionConfig(warning_threshold=1)
        assert config.warning_threshold == 1

        # 无效阈值应该失败
        with pytest.raises(Exception):  # Pydantic ValidationError
            LoopDetectionConfig(warning_threshold=0)

        with pytest.raises(Exception):
            LoopDetectionConfig(history_size=4)  # 最小为 5


# ============================================================================
# 数据模型测试
# ============================================================================


class TestToolCall:
    """测试 ToolCall"""

    def test_signature_simple(self):
        """测试简单签名"""
        call = ToolCall(tool_name="read", arguments={"path": "/tmp/file"})
        assert call.signature == "read"

    def test_signature_with_action(self):
        """测试带动作的签名"""
        call = ToolCall(
            tool_name="process",
            action="poll",
            arguments={"session_id": "123"},
        )
        assert call.signature == "process.poll"

    def test_content_hash(self):
        """测试内容哈希"""
        call1 = ToolCall(tool_name="read", arguments={"path": "/tmp/file"})
        call2 = ToolCall(tool_name="read", arguments={"path": "/tmp/file"})
        call3 = ToolCall(tool_name="read", arguments={"path": "/tmp/other"})

        # 相同参数应该产生相同哈希
        assert call1.content_hash() == call2.content_hash()
        # 不同参数应该产生不同哈希
        assert call1.content_hash() != call3.content_hash()


class TestToolResult:
    """测试 ToolResult"""

    def test_content_hash_empty(self):
        """测试空结果的哈希"""
        result = ToolResult(success=True, data=None)
        assert result.content_hash() is not None

    def test_content_hash_dict(self):
        """测试字典结果的哈希"""
        result1 = ToolResult(success=True, data={"status": "running", "count": 5})
        result2 = ToolResult(success=True, data={"status": "running", "count": 5})
        result3 = ToolResult(success=True, data={"status": "running", "count": 6})

        assert result1.content_hash() == result2.content_hash()
        assert result1.content_hash() != result3.content_hash()

    def test_content_hash_list(self):
        """测试列表结果的哈希"""
        result1 = ToolResult(success=True, data=[1, 2, 3])
        result2 = ToolResult(success=True, data=[1, 2, 3])
        result3 = ToolResult(success=True, data=[1, 2, 4])

        assert result1.content_hash() == result2.content_hash()
        assert result1.content_hash() != result3.content_hash()


# ============================================================================
# GenericRepeatDetector 测试
# ============================================================================


class TestGenericRepeatDetector:
    """测试通用重复检测器"""

    def test_no_detection_empty_history(self, default_config):
        """测试空历史不触发检测"""
        detector = GenericRepeatDetector()
        signal = detector.detect([], default_config)
        assert signal is None

    def test_no_detection_below_threshold(self, default_config):
        """测试低于阈值不触发"""
        detector = GenericRepeatDetector()
        history = [
            CallRecord(
                call=ToolCall(tool_name="read", arguments={"path": f"/tmp/file{i}"}),
                result=ToolResult(success=True),
            )
            for i in range(5)
        ]

        signal = detector.detect(history, default_config)
        assert signal is None

    def test_warning_threshold(self, strict_config):
        """测试警告阈值触发"""
        detector = GenericRepeatDetector()

        # 创建相同工具的重复调用
        history = [
            CallRecord(
                call=ToolCall(tool_name="read", arguments={"path": "/tmp/file"}),
                result=ToolResult(success=True),
            )
            for _ in range(3)  # 等于 warning_threshold
        ]

        signal = detector.detect(history, strict_config)
        assert signal is not None
        assert signal.level == LoopLevel.WARNING
        assert signal.detector == "genericRepeat"
        assert signal.score == 3

    def test_critical_threshold(self, strict_config):
        """测试严重阈值触发"""
        detector = GenericRepeatDetector()

        # 创建相同工具的大量重复调用
        history = [
            CallRecord(
                call=ToolCall(tool_name="read", arguments={"path": "/tmp/file"}),
                result=ToolResult(success=True),
            )
            for _ in range(5)  # 等于 critical_threshold
        ]

        signal = detector.detect(history, strict_config)
        assert signal is not None
        assert signal.level == LoopLevel.CRITICAL
        assert signal.score == 5

    def test_multiple_tools_detection(self, default_config):
        """测试多工具混合时的检测"""
        detector = GenericRepeatDetector()
        default_config.warning_threshold = 5

        # 混合调用，但 read 工具重复最多
        history = []
        for i in range(6):
            history.append(
                CallRecord(
                    call=ToolCall(tool_name="read", arguments={"path": f"/tmp/file{i}"}),
                    result=ToolResult(success=True),
                )
            )
            history.append(
                CallRecord(
                    call=ToolCall(tool_name="write", arguments={"path": f"/tmp/out{i}"}),
                    result=ToolResult(success=True),
                )
            )

        signal = detector.detect(history, default_config)
        # 两种工具各 6 次，应该触发 warning
        assert signal is not None


# ============================================================================
# KnownPollNoProgressDetector 测试
# ============================================================================


class TestKnownPollNoProgressDetector:
    """测试无进展轮询检测器"""

    def test_no_detection_non_poll(self, strict_config):
        """测试非轮询操作不触发"""
        detector = KnownPollNoProgressDetector()

        history = [
            CallRecord(
                call=ToolCall(tool_name="read", arguments={"path": "/tmp/file"}),
                result=ToolResult(success=True, data="content"),
            )
            for _ in range(5)
        ]

        signal = detector.detect(history, strict_config)
        assert signal is None

    def test_no_detection_with_progress(self, strict_config):
        """测试有进展的轮询不触发"""
        detector = KnownPollNoProgressDetector()

        # 每次结果都不同，表示有进展
        history = [
            CallRecord(
                call=ToolCall(tool_name="process", action="poll", arguments={"id": "123"}),
                result=ToolResult(success=True, data={"status": f"running_{i}"}),
            )
            for i in range(5)
        ]

        signal = detector.detect(history, strict_config)
        assert signal is None

    def test_detection_no_progress(self, strict_config):
        """测试无进展的轮询触发"""
        detector = KnownPollNoProgressDetector()

        # 相同的轮询结果，表示无进展
        history = [
            CallRecord(
                call=ToolCall(tool_name="process", action="poll", arguments={"id": "123"}),
                result=ToolResult(success=True, data={"status": "running"}),
            )
            for _ in range(5)
        ]

        signal = detector.detect(history, strict_config)
        assert signal is not None
        assert signal.level == LoopLevel.WARNING
        assert signal.detector == "knownPollNoProgress"

    def test_mixed_poll_tools(self, strict_config):
        """测试混合轮询工具"""
        detector = KnownPollNoProgressDetector()

        history = [
            CallRecord(
                call=ToolCall(tool_name="process", action="poll", arguments={"id": "1"}),
                result=ToolResult(success=True, data={"status": "running"}),
            ),
            CallRecord(
                call=ToolCall(tool_name="process", action="status", arguments={"id": "2"}),
                result=ToolResult(success=True, data={"status": "running"}),
            ),
            CallRecord(
                call=ToolCall(tool_name="process", action="poll", arguments={"id": "1"}),
                result=ToolResult(success=True, data={"status": "running"}),
            ),
            CallRecord(
                call=ToolCall(tool_name="session_status", arguments={"id": "3"}),
                result=ToolResult(success=True, data={"status": "running"}),
            ),
        ]

        signal = detector.detect(history, strict_config)
        # 混合调用，每组单独计算
        assert signal is None


# ============================================================================
# PingPongDetector 测试
# ============================================================================


class TestPingPongDetector:
    """测试乒乓消息检测器"""

    def test_no_detection_short_history(self, strict_config):
        """测试历史太短不触发"""
        detector = PingPongDetector()

        history = [
            CallRecord(
                call=ToolCall(tool_name="read", arguments={}),
                result=ToolResult(success=True),
            ),
            CallRecord(
                call=ToolCall(tool_name="write", arguments={}),
                result=ToolResult(success=True),
            ),
        ]

        signal = detector.detect(history, strict_config)
        assert signal is None

    def test_no_detection_no_pattern(self, strict_config):
        """测试无乒乓模式不触发"""
        detector = PingPongDetector()

        history = [
            CallRecord(
                call=ToolCall(tool_name="read", arguments={}),
                result=ToolResult(success=True),
            ),
            CallRecord(
                call=ToolCall(tool_name="write", arguments={}),
                result=ToolResult(success=True),
            ),
            CallRecord(
                call=ToolCall(tool_name="execute", arguments={}),
                result=ToolResult(success=True),
            ),
            CallRecord(
                call=ToolCall(tool_name="read", arguments={}),
                result=ToolResult(success=True),
            ),
        ]

        signal = detector.detect(history, strict_config)
        assert signal is None

    def test_detection_ping_pong(self, strict_config):
        """测试乒乓模式触发"""
        detector = PingPongDetector()

        # A -> B -> A -> B -> A -> B 模式
        history = []
        for _ in range(3):
            history.append(
                CallRecord(
                    call=ToolCall(tool_name="read", arguments={}),
                    result=ToolResult(success=True),
                )
            )
            history.append(
                CallRecord(
                    call=ToolCall(tool_name="write", arguments={}),
                    result=ToolResult(success=True),
                )
            )

        signal = detector.detect(history, strict_config)
        assert signal is not None
        assert signal.detector == "pingPong"

    def test_detection_with_other_tools(self, strict_config):
        """测试夹杂其他工具的乒乓模式"""
        detector = PingPongDetector()

        # A -> B -> C -> A -> B -> C 也可能触发
        history = []
        for _ in range(2):
            history.append(
                CallRecord(
                    call=ToolCall(tool_name="read", arguments={}),
                    result=ToolResult(success=True),
                )
            )
            history.append(
                CallRecord(
                    call=ToolCall(tool_name="write", arguments={}),
                    result=ToolResult(success=True),
                )
            )
            history.append(
                CallRecord(
                    call=ToolCall(tool_name="execute", arguments={}),
                    result=ToolResult(success=True),
                )
            )

        # 这种模式不会触发（因为需要 A -> B -> A -> B）
        signal = detector.detect(history, strict_config)
        assert signal is None


# ============================================================================
# LoopDetector 主控制器测试
# ============================================================================


class TestLoopDetector:
    """测试循环检测主控制器"""

    def test_initialization(self, default_config):
        """测试初始化"""
        detector = LoopDetector(default_config)

        assert detector.config.enabled is True
        assert len(detector._detectors) == 3  # 三个检测器

    def test_initialization_disabled_detectors(self):
        """测试禁用部分检测器"""
        config = LoopDetectionConfig(
            detectors=DetectorConfig(
                generic_repeat=True,
                known_poll_no_progress=False,
                ping_pong=False,
            )
        )
        detector = LoopDetector(config)

        assert len(detector._detectors) == 1

    def test_record_call(self, default_config):
        """测试记录调用"""
        detector = LoopDetector(default_config)

        call = ToolCall(tool_name="read", arguments={"path": "/tmp/file"})
        result = ToolResult(success=True, data="content")

        detector.record_call("agent-1", call, result)

        assert len(detector.get_history("agent-1")) == 1

    def test_record_call_disabled(self, disabled_config):
        """测试禁用时不记录"""
        detector = LoopDetector(disabled_config)

        call = ToolCall(tool_name="read", arguments={})
        result = ToolResult(success=True)

        detector.record_call("agent-1", call, result)

        assert len(detector.get_history("agent-1")) == 0

    def test_check_no_loop(self, default_config):
        """测试无循环时返回 None"""
        detector = LoopDetector(default_config)

        for i in range(5):
            call = ToolCall(tool_name=f"tool-{i}", arguments={})
            result = ToolResult(success=True)
            detector.record_call("agent-1", call, result)

        signal = detector.check("agent-1")
        assert signal is None

    def test_check_with_loop(self, strict_config):
        """测试检测到循环"""
        detector = LoopDetector(strict_config)

        # 创建重复调用
        for _ in range(5):
            call = ToolCall(tool_name="read", arguments={"path": "/tmp/file"})
            result = ToolResult(success=True)
            detector.record_call("agent-1", call, result)

        signal = detector.check("agent-1")
        assert signal is not None
        assert signal.level == LoopLevel.CRITICAL

    def test_global_circuit_breaker(self):
        """测试全局熔断器"""
        config = LoopDetectionConfig(
            global_circuit_breaker_threshold=5,
        )
        detector = LoopDetector(config)

        # 记录 5 次调用
        for i in range(5):
            call = ToolCall(tool_name=f"tool-{i}", arguments={})
            result = ToolResult(success=True)
            detector.record_call("agent-1", call, result)

        signal = detector.check("agent-1")
        assert signal is not None
        assert signal.level == LoopLevel.CIRCUIT_BREAKER

    def test_reset(self, default_config):
        """测试重置"""
        detector = LoopDetector(default_config)

        for i in range(10):
            call = ToolCall(tool_name="read", arguments={})
            result = ToolResult(success=True)
            detector.record_call("agent-1", call, result)

        assert len(detector.get_history("agent-1")) == 10

        detector.reset("agent-1")

        assert len(detector.get_history("agent-1")) == 0

    def test_agent_config_override(self, default_config, strict_config):
        """测试 agent 级配置覆盖"""
        detector = LoopDetector(default_config)
        detector.set_agent_config("agent-strict", strict_config)

        # agent-1 使用默认配置
        for _ in range(10):
            call = ToolCall(tool_name="read", arguments={})
            result = ToolResult(success=True)
            detector.record_call("agent-1", call, result)

        # agent-strict 使用严格配置
        for _ in range(5):
            call = ToolCall(tool_name="read", arguments={})
            result = ToolResult(success=True)
            detector.record_call("agent-strict", call, result)

        # agent-1 不应该触发（阈值 20）
        signal1 = detector.check("agent-1")
        assert signal1 is None or signal1.level == LoopLevel.WARNING

        # agent-strict 应该触发（阈值 5）
        signal2 = detector.check("agent-strict")
        assert signal2 is not None
        assert signal2.level == LoopLevel.CRITICAL

    def test_history_size_limit(self):
        """测试历史大小限制"""
        config = LoopDetectionConfig(history_size=10)
        detector = LoopDetector(config)

        # 记录 20 次调用
        for i in range(20):
            call = ToolCall(tool_name="read", arguments={"path": f"/tmp/file{i}"})
            result = ToolResult(success=True)
            detector.record_call("agent-1", call, result)

        # 历史应该被限制在 10 条
        assert len(detector.get_history("agent-1")) == 10

    def test_get_stats(self, default_config):
        """测试统计信息"""
        detector = LoopDetector(default_config)

        for i in range(5):
            call = ToolCall(tool_name="read", arguments={})
            result = ToolResult(success=True)
            detector.record_call("agent-1", call, result)

        for i in range(3):
            call = ToolCall(tool_name="write", arguments={})
            result = ToolResult(success=True)
            detector.record_call("agent-1", call, result)

        stats = detector.get_stats("agent-1")

        assert stats["total_calls"] == 8
        assert stats["unique_tools"] == 2
        assert stats["tool_distribution"]["read"] == 5
        assert stats["tool_distribution"]["write"] == 3

    def test_multiple_agents(self, default_config):
        """测试多 agent 隔离"""
        detector = LoopDetector(default_config)

        # agent-1 的调用
        for i in range(5):
            call = ToolCall(tool_name="read", arguments={})
            result = ToolResult(success=True)
            detector.record_call("agent-1", call, result)

        # agent-2 的调用
        for i in range(3):
            call = ToolCall(tool_name="write", arguments={})
            result = ToolResult(success=True)
            detector.record_call("agent-2", call, result)

        # 检查隔离
        assert len(detector.get_history("agent-1")) == 5
        assert len(detector.get_history("agent-2")) == 3

        stats1 = detector.get_stats("agent-1")
        stats2 = detector.get_stats("agent-2")

        assert stats1["tool_distribution"]["read"] == 5
        assert stats2["tool_distribution"]["write"] == 3


# ============================================================================
# 便捷函数测试
# ============================================================================


class TestConvenienceFunctions:
    """测试便捷函数"""

    def test_get_loop_detector(self):
        """测试获取全局实例"""
        from src.tools.guardrails import get_loop_detector, setup_loop_detector

        # 清理
        import src.tools.guardrails as module
        module._detector = None

        # 获取默认实例
        detector1 = get_loop_detector()
        assert detector1 is not None

        # 再次获取应该是同一个实例
        detector2 = get_loop_detector()
        assert detector1 is detector2

        # 设置新实例
        config = LoopDetectionConfig(warning_threshold=5)
        detector3 = setup_loop_detector(config)
        assert detector3.config.warning_threshold == 5

        # 获取的应该是新实例
        detector4 = get_loop_detector()
        assert detector4 is detector3


# ============================================================================
# 集成测试
# ============================================================================


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self):
        """测试完整工作流程"""
        config = LoopDetectionConfig(
            warning_threshold=3,
            critical_threshold=5,
            global_circuit_breaker_threshold=100,
        )
        detector = LoopDetector(config)

        # 模拟正常工作流
        calls = [
            ("read", {"path": "/src/main.py"}),
            ("write", {"path": "/src/output.py"}),
            ("execute", {"command": "python test.py"}),
            ("read", {"path": "/src/main.py"}),
            ("read", {"path": "/src/main.py"}),
            ("read", {"path": "/src/main.py"}),
        ]

        for tool_name, args in calls:
            call = ToolCall(tool_name=tool_name, arguments=args)
            result = ToolResult(success=True)
            detector.record_call("agent-1", call, result)

        # 应该检测到 read 工具重复
        signal = detector.check("agent-1")
        assert signal is not None
        assert signal.detector == "genericRepeat"
        assert signal.level == LoopLevel.WARNING

    def test_process_poll_scenario(self):
        """测试进程轮询场景"""
        config = LoopDetectionConfig(
            warning_threshold=3,
        )
        detector = LoopDetector(config)

        # 模拟进程轮询无进展
        for i in range(5):
            call = ToolCall(
                tool_name="process",
                action="poll",
                arguments={"session_id": "abc-123"},
            )
            # 每次都返回相同状态
            result = ToolResult(
                success=True,
                data={"status": "running", "exit_code": None},
            )
            detector.record_call("agent-1", call, result)

        signal = detector.check("agent-1")
        assert signal is not None
        assert signal.detector == "knownPollNoProgress"

    def test_ping_pong_scenario(self):
        """测试乒乓场景"""
        config = LoopDetectionConfig(
            warning_threshold=2,
        )
        detector = LoopDetector(config)

        # 模拟 A -> B -> A -> B -> A -> B
        tools = ["read", "write", "read", "write", "read", "write"]
        for tool in tools:
            call = ToolCall(tool_name=tool, arguments={})
            result = ToolResult(success=True)
            detector.record_call("agent-1", call, result)

        signal = detector.check("agent-1")
        assert signal is not None
        assert signal.detector == "pingPong"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
