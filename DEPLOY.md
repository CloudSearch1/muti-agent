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
