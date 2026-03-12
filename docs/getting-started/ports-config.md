# 端口配置说明

**最后更新**: 2026-03-12

---

## 服务端口一览

IntelliTeam 使用以下端口：

| 服务 | 端口 | 用途 | 配置项 |
|------|------|------|--------|
| **API 服务** | 8000 | REST API、Swagger 文档 | `API_PORT=8000` |
| **Web UI** | 8080 | 前端管理界面 | `WEBUI_PORT=8080` |
| **Redis** | 6379 | 缓存和消息队列 | `REDIS_URL` |
| **PostgreSQL** | 5432 | 数据库 | `DATABASE_URL` |

---

## 访问地址

### 开发环境

```bash
# API 服务
http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- 健康检查: http://localhost:8000/health

# Web UI
http://localhost:8080
- 管理界面: http://localhost:8080
- AI 助手: http://localhost:8080/ai-assistant.html
```

### 生产环境

```bash
# 绑定到所有网络接口
API_HOST=0.0.0.0
API_PORT=8000

# 通过 Nginx 反向代理时
# API: https://your-domain.com/api
# Web UI: https://your-domain.com
```

---

## 启动方式

### 方式 1: 使用启动脚本 (推荐)

```bash
# 启动 API 服务 + Web UI
python start.py
```

### 方式 2: 使用 CLI

```bash
# 启动 API 服务
python cli.py start

# 启动 Web UI
python cli.py webui

# 查看状态
python cli.py status
```

### 方式 3: 使用 make (Linux/Mac)

```bash
# 启动所有服务
make start

# 仅启动 API
make start-api

# 仅启动 Web UI
make start-webui
```

### 方式 4: 手动启动

```bash
# 启动 API 服务
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 启动 Web UI
python webui/app.py --host 0.0.0.0 --port 8080
```

---

## 生产环境部署示例

### 使用 Gunicorn

```bash
cd /path/to/intelliteam

# 启动 API 服务
gunicorn -w 4 \
  -k uvicorn.workers.UvicornWorker \
  src.main:app \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --keep-alive 5

# 启动 Web UI
gunicorn -w 2 \
  -k uvicorn.workers.UvicornWorker \
  webui.app:app \
  --bind 0.0.0.0:8080 \
  --timeout 60
```

### 使用 Docker

```bash
# 构建镜像
docker build -t intelliteam .

# 启动容器
docker run -d \
  --name intelliteam \
  -p 8000:8000 \
  -p 8080:8080 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/intelliteam" \
  -e OPENAI_API_KEY="sk-your-key" \
  intelliteam
```

---

## 端口冲突解决

### 检查端口占用

```bash
# Windows
netstat -ano | findstr :8000
netstat -ano | findstr :8080

# Linux/Mac
lsof -i :8000
lsof -i :8080
```

### 修改端口

如果端口被占用，可以在 `.env` 文件中修改：

```bash
# 修改 API 端口
API_PORT=8001

# 修改 Web UI 端口
WEBUI_PORT=8081
```

---

## 防火墙配置

### Ubuntu/Debian (ufw)

```bash
# 允许 API 端口
sudo ufw allow 8000/tcp

# 允许 Web UI 端口
sudo ufw allow 8080/tcp

# 查看状态
sudo ufw status
```

### CentOS/RHEL (firewalld)

```bash
# 允许 API 端口
sudo firewall-cmd --permanent --add-port=8000/tcp

# 允许 Web UI 端口
sudo firewall-cmd --permanent --add-port=8080/tcp

# 重载配置
sudo firewall-cmd --reload

# 查看状态
sudo firewall-cmd --list-all
```

### 云服务器安全组

- **阿里云**: 控制台 → ECS → 安全组 → 添加入方向规则
- **腾讯云**: 控制台 → 安全组 → 入站规则 → 添加规则
- **AWS**: EC2 → Security Groups → Inbound Rules

---

## 健康检查

### API 服务健康检查

```bash
curl http://localhost:8000/health
```

预期响应:
```json
{
  "status": "healthy",
  "timestamp": "2026-03-12T10:00:00",
  "services": {
    "database": "connected",
    "redis": "connected"
  }
}
```

### Web UI 健康检查

```bash
curl http://localhost:8080
```

预期响应: HTML 页面内容

---

## 环境变量优先级

1. **系统环境变量** (最高优先级)
2. **.env 文件**
3. **.env.example** (最低优先级)

---

## 常见问题

### Q: 无法访问服务？

**A**: 检查:
1. 服务是否启动成功
2. 端口是否正确
3. 防火墙/安全组是否放行
4. 绑定地址是否为 0.0.0.0 (生产环境)

### Q: 端口被占用？

**A**: 
1. 找到占用进程并终止
2. 或修改配置文件使用其他端口

### Q: 公网无法访问？

**A**: 检查:
1. 是否绑定到 0.0.0.0
2. 防火墙是否放行
3. 云服务商安全组配置
4. 路由器/交换机端口转发

---

## 参考资源

- [Docker 部署指南](docker-installation.md)
- [生产部署指南](production.md)
- [故障排查](../operations/troubleshooting.md)

---

*最后更新: 2026-03-12*  
*文档版本: v1.0*  
*维护者: @IntelliTeam*
