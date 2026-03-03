# Redis 快速安装指南

## 方法 1: 使用 Docker (推荐)

如果你已安装 Docker：

```bash
# 启动 Redis
docker run -d --name intelliteam-redis -p 6379:6379 redis:7-alpine

# 验证
docker ps | grep redis

# 测试连接
docker exec -it intelliteam-redis redis-cli ping
# 应返回：PONG

# 停止
docker stop intelliteam-redis

# 删除
docker rm intelliteam-redis
```

---

## 方法 2: Windows 本地安装

### 2.1 使用 Winget (Windows 包管理器)

```powershell
# 安装 Redis
winget install Microsoft.OpenRedis

# 启动服务
net start Redis

# 测试连接
redis-cli ping
```

### 2.2 使用 Chocolatey

```powershell
# 安装
choco install redis-64

# 启动
redis-server
```

### 2.3 手动安装

1. 下载 Windows 版 Redis: https://github.com/microsoftarchive/redis/releases
2. 解压到 `C:\Redis`
3. 运行 `redis-server.exe`
4. 测试：`redis-cli ping`

---

## 方法 3: 使用 WSL (Windows Subsystem for Linux)

```bash
# 在 WSL 中安装
sudo apt update
sudo apt install redis-server

# 启动
sudo service redis-server start

# 测试
redis-cli ping
```

---

## 验证 Redis 是否运行

### PowerShell

```powershell
# 检查端口
netstat -ano | findstr :6379

# 或使用 Telnet
telnet localhost 6379
```

### 测试连接

```bash
# 命令行
redis-cli ping
# 应返回：PONG

# Python
python -c "import redis; r = redis.Redis(); print(r.ping())"
# 应返回：True
```

---

## 常见问题

### Q1: 连接被拒绝 (Error 22)

**原因**: Redis 服务未启动

**解决**:
```bash
# Windows
net start Redis

# Linux
sudo service redis-server start

# Docker
docker start intelliteam-redis
```

### Q2: 端口被占用

**解决**: 修改 Redis 端口
```bash
redis-server --port 6380
```

然后修改 `.env`:
```bash
REDIS_URL=redis://localhost:6380/0
```

### Q3: 认证失败

**解决**: 设置密码
```bash
redis-server --requirepass your_password
```

修改 `.env`:
```bash
REDIS_URL=redis://:your_password@localhost:6379/0
```

---

## 推荐配置

对于 IntelliTeam 项目，推荐配置：

```bash
# 内存限制
maxmemory 256mb

# 内存淘汰策略
maxmemory-policy allkeys-lru

# 持久化 (可选)
save 900 1
save 300 10
save 60 10000

# 日志
loglevel notice
logfile redis.log
```

---

## 下一步

Redis 启动后，重新运行测试：

```bash
cd F:\ai_agent
python scripts/test_all.py
```

应该看到所有测试通过！✅

---

*最后更新：2026-03-03*
