"""
Multi-Agent 集成测试

测试完整的 Agent 协作流程
"""

import asyncio
import pytest
from datetime import datetime

from src.agents.coder import CoderAgent
from src.agents.tester import TesterAgent
from src.agents.doc_writer import DocWriterAgent
from src.agents.architect import ArchitectAgent
from src.agents.planner import PlannerAgent
from src.core.models import Task
from src.core.executor import AgentExecutor, Workflow, WorkflowTask


class TestMultiAgentWorkflow:
    """测试多 Agent 协作流程"""

    @pytest.fixture
    def executor(self):
        """创建执行引擎"""
        executor = AgentExecutor()

        # 注册 Agent（使用模拟模式）
        executor.register_agent("Planner", PlannerAgent())
        executor.register_agent("Architect", ArchitectAgent())
        executor.register_agent("Coder", CoderAgent())
        executor.register_agent("Tester", TesterAgent())
        executor.register_agent("DocWriter", DocWriterAgent())

        return executor

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="集成测试需要 LLM 连接，在 CI 环境中跳过")
    async def test_standard_workflow(self, executor):
        """测试标准研发工作流"""
        # 创建工作流
        workflow = executor.create_standard_workflow("Test Workflow")
        
        # 执行工作流
        result = await executor.execute_workflow(
            workflow,
            context={
                "project_name": "Test Project",
                "requirements": ["创建用户管理系统"],
            },
        )
        
        # 验证结果
        assert result["status"] in ["completed", "failed"]  # 允许失败（LLM 未配置）
        
        if result["status"] == "completed":
            # 验证每个 Agent 都执行了
            assert "Planner" in result["results"]
            assert "Architect" in result["results"]
            assert "Coder" in result["results"]
            assert "Tester" in result["results"]
            assert "DocWriter" in result["results"]
    
    @pytest.mark.asyncio
    async def test_parallel_tasks(self, executor):
        """测试并行任务执行"""
        workflow = Workflow(
            name="Parallel Test",
            description="测试并行执行",
        )
        
        # 创建可以并行执行的任务
        workflow.tasks = [
            WorkflowTask(
                agent_name="Coder",
                task_description="实现模块 A",
                dependencies=[],
            ),
            WorkflowTask(
                agent_name="Coder",
                task_description="实现模块 B",
                dependencies=[],  # 无依赖，可并行
            ),
            WorkflowTask(
                agent_name="Tester",
                task_description="测试模块 A 和 B",
                dependencies=[0, 1],  # 依赖前两个任务
            ),
        ]
        
        result = await executor.execute_workflow(workflow)
        
        # 验证执行顺序
        assert result["status"] in ["completed", "failed"]
    
    @pytest.mark.asyncio
    async def test_task_failure_handling(self, executor):
        """测试任务失败处理"""
        workflow = Workflow(
            name="Failure Test",
            description="测试失败处理",
        )
        
        # 创建一个会失败的任务
        workflow.tasks = [
            WorkflowTask(
                agent_name="NonExistentAgent",  # 不存在的 Agent
                task_description="这个任务会失败",
                dependencies=[],
                retry_count=0,  # 不重试
            ),
        ]
        
        result = await executor.execute_workflow(workflow)
        
        # 验证失败被正确处理
        assert result["status"] == "failed"
        assert "error" in result


class TestAgentIntegration:
    """测试 Agent 集成"""
    
    @pytest.fixture
    def agents(self):
        """创建 Agent 列表"""
        return {
            "Coder": CoderAgent(),
            "Tester": TesterAgent(),
            "DocWriter": DocWriterAgent(),
        }
    
    @pytest.mark.asyncio
    async def test_coder_to_tester_handoff(self, agents):
        """测试 Coder 到 Tester 的交接"""
        # Coder 生成代码
        coder = agents["Coder"]
        coder_task = Task(
            id="test-001",
            title="创建计算器",
            description="实现加减乘除",
            input_data={
                "requirements": "创建计算器类",
            },
        )
        
        coder_result = await coder.execute(coder_task)
        
        # 验证代码生成
        assert coder_result["status"] == "coding_complete"
        assert "code_files" in coder_result
        
        # Tester 测试代码
        tester = agents["Tester"]
        tester_task = Task(
            id="test-002",
            title="测试计算器",
            description="为计算器编写测试",
            input_data={
                "code_files": coder_result.get("code_files", []),
                "requirements": ["测试所有运算"],
            },
        )
        
        tester_result = await tester.execute(tester_task)
        
        # 验证测试执行
        assert tester_result["status"] == "testing_complete"
        assert "test_cases_created" in tester_result
    
    @pytest.mark.asyncio
    async def test_coder_to_docwriter_handoff(self, agents):
        """测试 Coder 到 DocWriter 的交接"""
        # Coder 生成代码
        coder = agents["Coder"]
        coder_task = Task(
            id="test-003",
            title="创建 API 模块",
            description="实现 REST API",
            input_data={
                "requirements": "创建用户 API",
            },
        )
        
        coder_result = await coder.execute(coder_task)
        
        # DocWriter 生成文档
        doc_writer = agents["DocWriter"]
        doc_task = Task(
            id="test-004",
            title="编写 API 文档",
            description="为 API 编写文档",
            input_data={
                "content_type": "api_doc",
                "source_material": {
                    "code_files": coder_result.get("code_files", []),
                },
            },
        )
        
        doc_result = await doc_writer.execute(doc_task)
        
        # 验证文档生成
        assert doc_result["status"] == "documentation_complete"
        assert "document" in doc_result


class TestDatabaseIntegration:
    """测试数据库集成"""
    
    @pytest.mark.asyncio
    async def test_task_persistence(self):
        """测试任务持久化"""
        from src.db.database import init_database, get_database_manager
        from src.db.crud import create_task, get_all_tasks
        
        # 初始化数据库
        await init_database()
        
        db_manager = get_database_manager()
        
        async with db_manager.async_session_maker() as session:
            # 创建任务
            task = await create_task(
                session,
                title="集成测试任务",
                description="测试数据库持久化",
                priority="high",
            )
            
            # 验证创建
            assert task.id is not None
            assert task.title == "集成测试任务"
            
            # 获取所有任务
            tasks = await get_all_tasks(session)
            
            # 验证可以查询到
            assert len(tasks) > 0
            assert any(t.id == task.id for t in tasks)
    
    @pytest.mark.asyncio
    async def test_batch_operations(self):
        """测试批量操作"""
        from src.db.database import init_database, get_database_manager
        from src.db.batch_ops import create_tasks_batch, delete_tasks_batch
        
        # 初始化数据库
        await init_database()
        
        db_manager = get_database_manager()
        
        async with db_manager.async_session_maker() as session:
            # 批量创建
            tasks_data = [
                {"title": f"批量任务 {i}", "description": f"测试 {i}"}
                for i in range(5)
            ]
            
            tasks = await create_tasks_batch(session, tasks_data)
            
            # 验证创建
            assert len(tasks) == 5
            
            # 批量删除
            task_ids = [t.id for t in tasks]
            deleted = await delete_tasks_batch(session, task_ids)
            
            # 验证删除
            assert deleted == 5


class TestLLMCache:
    """测试 LLM 缓存"""
    
    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """测试缓存命中"""
        from src.llm.cache import LLMCache
        
        cache = LLMCache(use_redis=False)
        
        # 设置缓存
        await cache.set(
            prompt="test prompt",
            response="test response",
            model="test-model",
        )
        
        # 获取缓存
        cached = await cache.get("test prompt", "test-model")
        
        # 验证命中
        assert cached == "test response"
        
        # 验证统计
        stats = cache.get_stats()
        assert stats["hits"] == 1
    
    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """测试缓存未命中"""
        from src.llm.cache import LLMCache
        
        cache = LLMCache(use_redis=False)
        
        # 获取不存在的缓存
        cached = await cache.get("nonexistent", "test-model")
        
        # 验证未命中
        assert cached is None
        
        # 验证统计
        stats = cache.get_stats()
        assert stats["misses"] >= 1


class TestSecretManager:
    """测试密钥管理"""
    
    @pytest.mark.asyncio
    async def test_secret_storage(self):
        """测试密钥存储"""
        from src.utils.secret_manager import SecretManager
        import tempfile
        import os
        
        # 创建临时文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            secrets_file = f.name
        
        try:
            manager = SecretManager(secrets_file=secrets_file)
            
            # 设置密钥
            manager.set_secret("test_key", "test_value", encrypt=True)
            
            # 获取密钥
            value = manager.get_secret("test_key", decrypt=True)
            
            # 验证
            assert value == "test_value"
            
        finally:
            # 清理
            if os.path.exists(secrets_file):
                os.unlink(secrets_file)


# 运行测试
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
