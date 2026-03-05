# 🚀 IntelliTeam 部署指南

## 快速部署

### 方法 1: Docker Compose (推荐)

```bash
# 启动所有服务
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 方法 2: 手动部署

```bash
# 安装依赖
pip install -r requirements.txt

# 启动 API 服务
python start.py

# 启动 Web UI
python webui/server_v3.py
```

## 访问地址

| 服务 | 地址 | 状态 |
|------|------|------|
| API 文档 | http://localhost:8000/docs | ✅ |
| Web UI | http://localhost:3000 | ✅ |
| 健康检查 | http://localhost:3000/api/v1/health | ✅ |

## 环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
OPENAI_API_KEY=sk-xxx
OPENAI_API_BASE=https://coding.dashscope.aliyuncs.com/v1
OPENAI_MODEL=qwen3.5-plus
```

## 监控

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3001

---
*使用 devops skill 自动生成*
