#!/bin/bash
# IntelliTeam 生产环境启动脚本
# 支持公网访问

echo "🚀 启动 IntelliTeam 生产服务器..."
echo ""

# 获取本机IP
LOCAL_IP=$(hostname -I | awk '{print $1}')
echo "本机IP: $LOCAL_IP"
echo ""

# 方式1: 使用 Gunicorn + Uvicorn (推荐用于生产)
echo "方式1: Gunicorn + Uvicorn"
echo "命令: gunicorn -w 4 -k uvicorn.workers.UvicornWorker webui.app:app --bind 0.0.0.0:8080 --forwarded-allow-ips='*' --proxy-allow-from='*'"
echo ""

# 方式2: 直接使用 Uvicorn (开发环境)
echo "方式2: Uvicorn (开发)"
echo "命令: python3 webui/app.py"
echo ""

# 方式3: 使用 Gunicorn 配置文件
echo "方式3: Gunicorn 配置文件"
echo "命令: gunicorn -c gunicorn.conf.py webui.app:app"
echo ""

# 检查端口是否被占用
if lsof -Pi :8080 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️ 警告: 端口 8080 已被占用"
    echo "请使用其他端口或停止占用该端口的服务"
    exit 1
fi

# 默认使用方式1启动
echo "正在使用 Gunicorn 启动..."
gunicorn -w 4 -k uvicorn.workers.UvicornWorker webui.app:app \
    --bind 0.0.0.0:8080 \
    --forwarded-allow-ips='*' \
    --proxy-allow-from='*' \
    --access-logfile - \
    --error-logfile - \
    --log-level info
