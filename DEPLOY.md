# IntelliTeam 部署教程

## 项目信息

- **项目地址**: https://github.com/CloudSearch1/muti-agent
- **Python版本**: >= 3.11
- **默认端口**: 8080

---

## 快速部署

### 1. 环境要求

- Python 3.11 或更高版本
- pip 包管理器
- Git (可选，用于克隆)

### 2. 克隆项目

```bash
git clone git@github.com:CloudSearch1/muti-agent.git
cd muti-agent
```

### 3. 创建虚拟环境（推荐）

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

### 4. 安装依赖

```bash
pip install -r requirements.txt
```

### 5. 启动服务

```bash
python3 webui/app.py
```

### 6. 访问应用

- 主页: http://127.0.0.1:8080
- AI助手: http://127.0.0.1:8080/ai-assistant.html

---

## 生产环境部署

### 使用 Gunicorn + Uvicorn

```bash
pip install gunicorn

# 启动（4个工作进程）
gunicorn -w 4 -k uvicorn.workers.UvicornWorker webui.app:app --bind 0.0.0.0:8080
```

**重要**：启动 Gunicorn 时，请确保在项目根目录执行命令：
```bash
cd /path/to/muti-agent
gunicorn -w 4 -k uvicorn.workers.UvicornWorker webui.app:app --bind 0.0.0.0:8080
```

### 生产环境配置建议

```bash
# 推荐的生产启动命令
gunicorn -w 4 \
  -k uvicorn.workers.UvicornWorker \
  webui.app:app \
  --bind 0.0.0.0:8080 \
  --timeout 120 \
  --keep-alive 5 \
  --access-logfile - \
  --error-logfile - \
  --log-level info
```

### 使用 Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["python", "webui/app.py"]
```

构建并运行：
```bash
docker build -t intelliteam .
docker run -p 8080:8080 intelliteam
```

### 使用 systemd 服务（Linux）

创建服务文件 `/etc/systemd/system/intelliteam.service`：

```ini
[Unit]
Description=IntelliTeam Multi-Agent Platform
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/muti-agent
Environment=PYTHONPATH=/path/to/muti-agent
ExecStart=/path/to/muti-agent/venv/bin/python webui/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

启用并启动：
```bash
sudo systemctl enable intelliteam
sudo systemctl start intelliteam
```

---

## 配置说明

### 环境变量

创建 `.env` 文件：

```env
# 数据库
DATABASE_URL=sqlite:///./intelliteam.db

# Redis（可选）
REDIS_URL=redis://localhost:6379/0

# JWT密钥
SECRET_KEY=your-secret-key-here

# 调试模式
DEBUG=false

# 主机和端口
HOST=0.0.0.0
PORT=8080
```

### 主要目录结构

```
muti-agent/
├── src/                    # 后端源代码
│   ├── agents/            # Agent实现
│   ├── api/               # API路由
│   ├── core/              # 核心功能
│   └── ...
├── webui/                 # 前端文件
│   ├── index_v5.html      # 主页面
│   ├── ai-assistant.html  # AI助手页面
│   └── app.py             # Web服务器
├── tests/                 # 测试文件
├── requirements.txt       # Python依赖
└── pyproject.toml         # 项目配置
```

---

## 常见问题

### Q: Python版本不满足？

A: 安装Python 3.11或更高版本：
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-pip

# macOS
brew install python@3.11
```

### Q: 端口被占用？

A: 修改启动端口：
```bash
python3 webui/app.py --port 8081
```

### Q: 如何后台运行？

A: 使用 nohup 或 screen：
```bash
nohup python3 webui/app.py > app.log 2>&1 &
```

### Q: 如何更新代码？

A: 拉取最新代码并重启：
```bash
git pull origin main
pip install -r requirements.txt
# 重启服务
```

---

## 故障排查

### Q: 无法通过公网 IP 访问？

按以下步骤检查：

**1. 确认服务正在监听**
```bash
# 检查端口监听状态
netstat -tlnp | grep 8080
# 或
ss -tlnp | grep 8080

# 应该看到类似输出：
# tcp  0  0  0.0.0.0:8080  0.0.0.0:*  LISTEN  pid/gunicorn
```

**2. 测试本地访问**
```bash
# 在服务器上测试
curl http://127.0.0.1:8080
curl http://服务器内网IP:8080
```

**3. 检查防火墙**
```bash
# Ubuntu/Debian
sudo ufw status
sudo ufw allow 8080/tcp

# CentOS/RHEL
sudo firewall-cmd --list-all
sudo firewall-cmd --add-port=8080/tcp --permanent
sudo firewall-cmd --reload

# iptables
sudo iptables -L -n | grep 8080
sudo iptables -I INPUT -p tcp --dport 8080 -j ACCEPT
```

**4. 检查云服务商安全组**
- 阿里云：安全组规则 → 添加入方向规则 → 端口 8080
- 腾讯云：安全组 → 入站规则 → 添加 TCP 8080
- AWS：Security Groups → Inbound Rules → Add Rule → TCP 8080

**5. 确认绑定地址正确**
```bash
# 错误：只监听本地回环地址
gunicorn ... --bind 127.0.0.1:8080  # ❌ 无法公网访问

# 正确：监听所有网络接口
gunicorn ... --bind 0.0.0.0:8080    # ✅ 可以公网访问
```

**6. 检查工作目录**
```bash
# 确保在项目根目录启动
cd /path/to/muti-agent
gunicorn -w 4 -k uvicorn.workers.UvicornWorker webui.app:app --bind 0.0.0.0:8080
```

### Q: 访问返回 500 错误？

检查日志输出：
```bash
# 查看详细错误
gunicorn ... --log-level debug
```

常见原因：
- 静态文件目录不存在
- HTML 模板文件缺失
- Python 依赖未安装

### Q: WebSocket 连接失败？

如果使用了反向代理（如 Nginx），需要配置 WebSocket 支持：
```nginx
location /ws {
    proxy_pass http://127.0.0.1:8080;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}
```

---

## 开发模式

### 运行测试

```bash
python3 -m pytest tests/ -v
```

### 代码格式化

```bash
black src/
ruff check src/
```

---

## 技术支持

- GitHub Issues: https://github.com/CloudSearch1/muti-agent/issues
- 文档: https://docs.openclaw.ai

---

**部署完成！** 🎉
