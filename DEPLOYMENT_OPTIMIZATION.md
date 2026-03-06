# Docker 部署优化

## 多阶段构建

```dockerfile
# 构建阶段
FROM python:3.11-slim as builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# 运行阶段
FROM python:3.11-slim

WORKDIR /app

# 创建非 root 用户
RUN useradd -m -u 1000 appuser

# 从构建阶段复制依赖
COPY --from=builder /root/.local /home/appuser/.local

# 复制应用代码
COPY --chown=appuser:appuser . .

# 设置环境变量
ENV PATH=/home/appuser/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 切换到非 root 用户
USER appuser

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8080/health')" || exit 1

# 启动命令
CMD ["python", "webui/app_db.py"]
```

## Docker Compose 优化

```yaml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8080:8080"
    environment:
      - DB_URL=postgresql+asyncpg://user:pass@db:5432/intelliteam
      - REDIS_ENABLED=true
      - REDIS_HOST=redis
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./logs:/app/logs
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
    restart: unless-stopped

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=pass
      - POSTGRES_DB=intelliteam
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U user"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

## 性能优化建议

### 1. 使用 Alpine 基础镜像
```dockerfile
FROM python:3.11-alpine
```

### 2. 减少镜像层数
```dockerfile
# 合并 RUN 命令
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
```

### 3. 使用 .dockerignore
```
__pycache__/
*.pyc
*.pyo
.git/
.env
logs/
*.log
.pytest_cache/
.coverage
htmlcov/
```

### 4. 启用构建缓存
```bash
docker build --cache-from myapp:latest -t myapp:latest .
```

### 5. 使用 BuildKit
```bash
export DOCKER_BUILDKIT=1
docker build -t myapp:latest .
```

## 部署脚本

```bash
#!/bin/bash

# 构建镜像
docker build -t intelliteam:latest .

# 停止旧容器
docker stop intelliteam || true
docker rm intelliteam || true

# 启动新容器
docker run -d \
  --name intelliteam \
  -p 8080:8080 \
  -e DB_URL=postgresql+asyncpg://user:pass@localhost:5432/intelliteam \
  -e REDIS_ENABLED=true \
  -v $(pwd)/logs:/app/logs \
  --restart unless-stopped \
  intelliteam:latest

# 查看日志
docker logs -f intelliteam
```

## 监控和优化

```bash
# 查看容器资源使用
docker stats intelliteam

# 查看容器详情
docker inspect intelliteam

# 进入容器调试
docker exec -it intelliteam /bin/bash

# 清理未使用的镜像
docker image prune -a

# 清理未使用的卷
docker volume prune
```
