"""
性能基准测试脚本

使用 locust 进行压力测试
"""

from locust import HttpUser, task, between, events
import json
import random


class IntelliTeamUser(HttpUser):
    """模拟用户行为"""
    
    # 等待时间 1-3 秒
    wait_time = between(1, 3)
    
    # 测试数据
    task_ids = list(range(1, 101))
    
    def on_start(self):
        """用户开始时的初始化"""
        # 登录获取 token
        response = self.client.post(
            "/api/v1/auth/login",
            json={"username": "test", "password": "test123"}
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            self.client.headers["Authorization"] = f"Bearer {token}"
    
    @task(10)
    def get_tasks(self):
        """获取任务列表"""
        self.client.get("/api/v1/tasks")
    
    @task(5)
    def get_task_detail(self):
        """获取任务详情"""
        task_id = random.choice(self.task_ids)
        self.client.get(f"/api/v1/tasks/{task_id}")
    
    @task(3)
    def create_task(self):
        """创建任务"""
        self.client.post(
            "/api/v1/tasks",
            json={
                "title": f"Test Task {random.randint(1, 1000)}",
                "description": "Test description",
                "priority": "normal"
            }
        )
    
    @task(2)
    def get_agents(self):
        """获取 Agent 列表"""
        self.client.get("/api/v1/agents")
    
    @task(1)
    def get_stats(self):
        """获取统计信息"""
        self.client.get("/api/v1/stats")
    
    @task(1)
    def get_metrics(self):
        """获取 Prometheus 指标"""
        self.client.get("/metrics")


class HeavyUser(HttpUser):
    """重度用户"""
    
    wait_time = between(0.5, 1)
    
    @task
    def stress_test(self):
        """压力测试"""
        # 并发获取多个资源
        with self.client.get("/api/v1/tasks", catch_response=True) as response:
            if response.status_code != 200:
                response.failure("获取任务失败")
        
        with self.client.get("/api/v1/agents", catch_response=True) as response:
            if response.status_code != 200:
                response.failure("获取 Agent 失败")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """测试开始时"""
    print("🚀 性能测试开始")
    print(f"目标地址：{environment.host}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """测试结束时"""
    print("✅ 性能测试完成")
    
    # 打印统计
    stats = environment.stats
    print(f"\n📊 测试结果:")
    print(f"总请求数：{stats.total.num_requests}")
    print(f"失败请求数：{stats.total.num_failures}")
    print(f"成功率：{(1 - stats.total.fail_ratio) * 100:.2f}%")
    print(f"平均响应时间：{stats.total.avg_response_time:.2f}ms")
    print(f"QPS: {stats.total.current_rps:.2f}")


if __name__ == "__main__":
    import os
    os.system("locust -f locustfile.py --host=http://localhost:8080")
