# 生产环境部署指南

## 快速部署

### 1. Docker 部署（推荐）

```bash
# 复制生产环境配置
cp .env.example .env

# 编辑 .env 文件，填入 API Key 和其他配置

# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f intelliteam

# 停止服务
docker-compose down
```

### 2. 服务访问

- **API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **Prometheus**: http://localhost:9091
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379
- **Milvus**: localhost:19530

---

## 手动部署

### 系统要求

- Python 3.11+
- PostgreSQL 15+
- Redis 7.0+
- Milvus 2.3+

### 安装步骤

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件

# 3. 初始化数据库
python -c "from src.db import get_database_manager; import asyncio; asyncio.get_event_loop().run_until_complete(get_database_manager().create_tables())"

# 4. 启动服务
python -m src.main_prod
```

---

## 配置说明

### 环境变量

```bash
# 应用配置
APP_ENV=production
DEBUG=false
LOG_LEVEL=WARNING

# LLM 配置
OPENAI_API_KEY=your-api-key
OPENAI_API_BASE=https://coding.dashscope.aliyuncs.com/v1
OPENAI_MODEL=qwen3.5-plus

# 数据库
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/intelliteam
REDIS_URL=redis://localhost:6379/0

# API 配置
API_WORKERS=4
JWT_SECRET_KEY=your-secret-key
```

---

## 监控

### Prometheus 指标

- `http_requests_total` - HTTP 请求总数
- `http_request_duration_seconds` - HTTP 请求耗时
- `agent_tasks_total` - Agent 任务执行数
- `agent_execution_time_seconds` - Agent 执行耗时
- `workflow_executions_total` - 工作流执行数

### 日志

日志文件位于 `logs/intelliteam.log`

```bash
# 查看实时日志
tail -f logs/intelliteam.log

# 查看错误日志
grep ERROR logs/intelliteam.log
```

---

## 性能优化

### 1. 调整 Worker 数量

```bash
# 根据 CPU 核心数调整
API_WORKERS=$(nproc)
```

### 2. 数据库连接池

```python
# 在 settings.py 中调整
pool_size=20
max_overflow=10
```

### 3. Redis 缓存

```python
# 设置合理的 TTL
AGENT_CACHE_TTL = 3600  # 1 小时
```

---

## 安全建议

1. **修改默认密码**
   - PostgreSQL: `password`
   - Redis: 无密码
   - MinIO: `minioadmin`

2. **启用 HTTPS**
   - 使用 Nginx 反向代理
   - 配置 SSL 证书

3. **限制 CORS**
   ```bash
   CORS_ORIGINS=["https://your-domain.com"]
   ```

4. **设置速率限制**
   ```bash
   RATE_LIMIT_PER_MINUTE=60
   ```

---

## 故障排查

### 服务无法启动

```bash
# 检查日志
docker-compose logs intelliteam

# 检查依赖服务
docker-compose ps
```

### 数据库连接失败

```bash
# 测试 PostgreSQL 连接
docker-compose exec postgres psql -U intelliteam -c "SELECT 1"

# 测试 Redis 连接
docker-compose exec redis redis-cli ping
```

### 内存不足

```bash
# 调整 Docker 资源限制
# 编辑 docker-compose.yml 中的 deploy.resources
```

---

## 备份和恢复

### 数据库备份

```bash
# 备份 PostgreSQL
docker-compose exec postgres pg_dump -U intelliteam intelliteam > backup.sql

# 恢复
docker-compose exec -T postgres psql -U intelliteam < backup.sql
```

### Redis 备份

```bash
# 保存数据
docker-compose exec redis redis-cli SAVE

# 备份 RDB 文件
docker cp intelliteam-redis:/data/dump.rdb ./backup.rdb
```

---

*最后更新：2026-03-03*
