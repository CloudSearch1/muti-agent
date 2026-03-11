# IntelliTeam 部署指南

> **生产环境部署完整指南**

---

## 📋 目录

1. [部署准备](#部署准备)
2. [Docker 部署](#docker 部署)
3. [Kubernetes 部署](#kubernetes 部署)
4. [配置说明](#配置说明)
5. [监控告警](#监控告警)
6. [备份恢复](#备份恢复)
7. [故障排查](#故障排查)

---

## 部署准备

### 系统要求

**最低配置**:
- CPU: 4 核
- 内存：8GB
- 磁盘：50GB
- 网络：100Mbps

**推荐配置**:
- CPU: 8 核
- 内存：16GB
- 磁盘：100GB SSD
- 网络：1Gbps

### 依赖服务

- **Redis**: 6.0+ (缓存和消息队列)
- **PostgreSQL**: 13+ (数据库)
- **Celery**: 5.0+ (任务队列)
- **Prometheus**: 2.30+ (监控)
- **Grafana**: 8.0+ (可视化)

### 环境变量

创建 `.env` 文件：

```bash
# 应用配置
APP_ENV=production
DEBUG=false
SECRET_KEY=your-secret-key-here

# 数据库
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/intelliteam

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1

# LLM
OPENAI_API_KEY=your-api-key
OPENAI_API_BASE=https://api.openai.com/v1

# 安全
CORS_ORIGINS=["https://your-domain.com"]
RATE_LIMIT_PER_MINUTE=60
```

---

## Docker 部署

### 1. 构建镜像

```bash
# 构建应用镜像
docker build -t intelliteam:latest .

# 构建 worker 镜像
docker build -t intelliteam-worker:latest -f Dockerfile.worker .
```

### 2. 启动服务

```bash
# 使用 docker-compose
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 3. 服务列表

```yaml
services:
  - api (API 服务)
  - worker (Celery Worker)
  - beat (Celery Beat)
  - redis (Redis 缓存)
  - postgres (PostgreSQL 数据库)
  - prometheus (Prometheus 监控)
  - grafana (Grafana 可视化)
```

---

## Kubernetes 部署

### 1. 创建命名空间

```bash
kubectl create namespace intelliteam
```

### 2. 部署应用

```bash
# 应用配置
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml

# 部署应用
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml

# 部署 Worker
kubectl apply -f k8s/worker-deployment.yaml

# 部署监控
kubectl apply -f k8s/prometheus.yaml
kubectl apply -f k8s/grafana.yaml
```

### 3. 检查状态

```bash
# 查看 Pod 状态
kubectl get pods -n intelliteam

# 查看服务状态
kubectl get svc -n intelliteam

# 查看日志
kubectl logs -f deployment/intelliteam -n intelliteam
```

---

## 配置说明

### 生产环境配置

```python
# .env.production
APP_ENV=production
DEBUG=false
LOG_LEVEL=WARNING

# 数据库连接池
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=10

# Redis
REDIS_MAX_CONNECTIONS=50

# Celery
CELERY_WORKER_CONCURRENCY=4
CELERY_TASK_ACKS_LATE=true

# 安全
SECRET_KEY=change-me-in-production
JWT_EXPIRE_HOURS=24
```

### 性能优化配置

```python
# 缓存配置
CACHE_TTL=300  # 5 分钟
CACHE_MAX_SIZE=1000

# 限流配置
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# 超时配置
REQUEST_TIMEOUT=30
CELERY_TASK_TIMEOUT=300
```

---

## 监控告警

### Prometheus 配置

```yaml
# prometheus.yml
scrape_configs:
  - job_name: 'intelliteam'
    static_configs:
      - targets: ['api:8000']
    metrics_path: '/metrics'
    scrape_interval: 15s
```

### 告警规则

```yaml
# alerts.yml
groups:
  - name: intelliteam
    rules:
      - alert: HighAPIErrorRate
        expr: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m])) > 0.05
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "API 错误率过高"
```

### Grafana 仪表盘

导入以下仪表盘：
- **API 性能监控** (ID: 10001)
- **系统资源监控** (ID: 10002)
- **Celery 任务监控** (ID: 10003)
- **业务指标监控** (ID: 10004)

---

## 备份恢复

### 数据库备份

```bash
# 备份数据库
pg_dump -U intelliteam intelliteam > backup_$(date +%Y%m%d).sql

# 压缩备份
pg_dump -U intelliteam intelliteam | gzip > backup_$(date +%Y%m%d).sql.gz

# 恢复数据库
psql -U intelliteam intelliteam < backup_20260303.sql
```

### Redis 备份

```bash
# 触发 Redis 保存
redis-cli BGSAVE

# 备份 RDB 文件
cp /var/lib/redis/dump.rdb /backup/redis-dump-$(date +%Y%m%d).rdb

# 恢复 Redis
cp /backup/redis-dump-20260303.rdb /var/lib/redis/dump.rdb
redis-cli BGREWRITEAOF
```

### 日志备份

```bash
# 日志轮转配置
# /etc/logrotate.d/intelliteam
/var/log/intelliteam/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 www-data www-data
}
```

---

## 故障排查

### API 无法访问

```bash
# 检查服务状态
docker-compose ps api

# 查看日志
docker-compose logs api

# 检查端口
netstat -tlnp | grep 8000

# 测试健康检查
curl http://localhost:8000/health
```

### 任务执行失败

```bash
# 检查 Celery Worker
docker-compose ps worker

# 查看 Worker 日志
docker-compose logs worker

# 检查 Redis
docker-compose exec redis redis-cli ping

# 检查任务队列
docker-compose exec redis redis-cli llen celery
```

### 数据库连接失败

```bash
# 检查 PostgreSQL
docker-compose ps postgres

# 测试连接
docker-compose exec postgres psql -U intelliteam -c "SELECT 1"

# 查看连接数
docker-compose exec postgres psql -U intelliteam -c "SELECT count(*) FROM pg_stat_activity"
```

### 性能问题

```bash
# 查看系统资源
docker stats

# 查看慢查询
docker-compose exec postgres psql -U intelliteam -c "SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10"

# 查看缓存命中率
docker-compose exec redis redis-cli info stats | grep hits
```

---

## 性能基准

### 预期性能指标

**API 性能**:
- QPS: 1000+
- 平均响应时间：<100ms
- P95 响应时间：<500ms
- P99 响应时间：<1s

**Celery 任务**:
- 任务处理速度：100 任务/秒
- 任务失败率：<1%
- 任务平均耗时：<5s

**缓存性能**:
- 缓存命中率：>80%
- 缓存响应时间：<10ms

**数据库性能**:
- 查询响应时间：<50ms
- 连接池利用率：<80%

---

## 安全建议

### 网络安全

- ✅ 使用 HTTPS
- ✅ 配置防火墙
- ✅ 限制访问 IP
- ✅ 使用 VPN 访问管理界面

### 应用安全

- ✅ 定期更新依赖
- ✅ 使用强密码
- ✅ 启用双因素认证
- ✅ 定期审计日志

### 数据安全

- ✅ 加密敏感数据
- ✅ 定期备份
- ✅ 访问控制
- ✅ 数据脱敏

---

## 公网访问问题排查

### 快速排查

使用一键排查脚本：

```bash
# 运行排查脚本
./scripts/check_network.sh
```

### 常见原因

1. **云服务器安全组未配置** (90% 案例)
   - 阿里云：控制台 → ECS → 安全组 → 添加入方向规则 TCP 8080
   - AWS：EC2 → Security Groups → Add Inbound Rule TCP 8080

2. **服务器防火墙阻止**
   ```bash
   # Ubuntu/Debian (ufw)
   sudo ufw allow 8080/tcp

   # CentOS/RHEL (firewalld)
   sudo firewall-cmd --permanent --add-port=8080/tcp
   sudo firewall-cmd --reload
   ```

3. **端口绑定错误**
   - 确保 Gunicorn 绑定 `0.0.0.0:8080`，而非 `127.0.0.1:8080`

### 详细排查指南

参见 [公网访问排查指南](./公网访问排查指南.md)

---

*持续更新中...* 🚀
