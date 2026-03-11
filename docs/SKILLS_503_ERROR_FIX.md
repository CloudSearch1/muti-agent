# Skills API 503 错误解决方案

## 问题现象
- 浏览器控制台报错：`加载技能失败: SyntaxError: Unexpected token '<', "<html>\n<h"... is not valid JSON`
- 直接curl测试返回：`HTTP/1.1 503 Service Unavailable`
- 健康检查接口 `/api/v1/health` 正常

## 原因分析

503错误通常表示：
1. Gunicorn worker 过载或崩溃
2. 请求被排队等待处理
3. Worker 数量不足

## 解决方案

### 方案1：增加 Gunicorn Worker 数量

```bash
# 当前使用4个worker，增加到8个
gunicorn -w 8 -k uvicorn.workers.UvicornWorker webui.app:app \
    --bind 0.0.0.0:8080 \
    --forwarded-allow-ips='*' \
    --proxy-allow-from='*' \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 50
```

### 方案2：使用异步 worker

```bash
# 使用 gevent worker（更好的并发处理）
pip install gevent

gunicorn -w 4 -k gevent webui.app:app \
    --bind 0.0.0.0:8080 \
    --worker-connections 1000 \
    --timeout 120
```

### 方案3：重启服务

```bash
# 查找并停止现有gunicorn进程
pkill -f gunicorn

# 等待几秒
sleep 3

# 重新启动
./start_production.sh
```

### 方案4：检查服务器资源

```bash
# 检查CPU使用率
top -bn1 | head -20

# 检查内存使用
free -h

# 检查磁盘空间
df -h

# 检查连接数
netstat -an | grep :8080 | wc -l
```

### 方案5：调整 Gunicorn 配置

编辑 `gunicorn.conf.py`：

```python
# 增加worker数量
workers = 8  # 原来是 CPU*2+1，现在直接设为8

# 增加超时时间
timeout = 120

# 增加保持连接时间
keepalive = 5

# 启用预加载（减少内存使用）
preload_app = True

# 每个worker最大请求数（防止内存泄漏）
max_requests = 500
max_requests_jitter = 50

# 启用异步模式
worker_class = "uvicorn.workers.UvicornWorker"
```

然后启动：
```bash
gunicorn -c gunicorn.conf.py webui.app:app
```

## 推荐的启动命令

```bash
#!/bin/bash
# start_optimized.sh - 优化的启动脚本

# 停止现有服务
pkill -f gunicorn
sleep 2

# 获取CPU核心数
CPU_COUNT=$(nproc)
WORKER_COUNT=$((CPU_COUNT * 2 + 1))

echo "启动 IntelliTeam (优化配置)..."
echo "CPU核心数: $CPU_COUNT"
echo "Worker数量: $WORKER_COUNT"

gunicorn -k uvicorn.workers.UvicornWorker webui.app:app \
    --bind 0.0.0.0:8080 \
    --workers $WORKER_COUNT \
    --worker-connections 1000 \
    --timeout 120 \
    --keep-alive 5 \
    --max-requests 500 \
    --max-requests-jitter 50 \
    --forwarded-allow-ips='*' \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --preload
```

## 监控命令

```bash
# 实时监控Gunicorn状态
watch -n 1 'ps aux | grep gunicorn | grep -v grep'

# 查看错误日志
tail -f /var/log/gunicorn/error.log

# 查看访问日志
tail -f /var/log/gunicorn/access.log

# 检查端口监听
ss -tlnp | grep 8080
```

## 浏览器端解决方案

如果服务器端正常，可能是浏览器缓存问题：

1. **强制刷新页面**：Ctrl + F5 (Windows) 或 Cmd + Shift + R (Mac)
2. **清除浏览器缓存**
3. **使用无痕模式测试**
4. **检查浏览器控制台网络请求**

## 测试命令

```bash
# 测试skills API
curl -s http://47.253.152.159:8080/api/v1/skills/ | python3 -m json.tool

# 带重定向跟踪测试
curl -sL http://47.253.152.159:8080/api/v1/skills | python3 -m json.tool

# 检查响应头
curl -sI http://47.253.152.159:8080/api/v1/skills/
```

## 总结

最可能的原因是：
1. Gunicorn worker 数量不足（当前4个，建议8个）
2. Worker 过载或崩溃
3. 需要重启服务

建议立即执行：**重启服务并增加worker数量**
