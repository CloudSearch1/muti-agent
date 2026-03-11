# Gunicorn 配置文件
# 用于生产环境部署

import multiprocessing

# 服务器绑定
bind = "0.0.0.0:8080"

# 工作进程数
workers = multiprocessing.cpu_count() * 2 + 1

# 工作进程类型（使用 Uvicorn）
worker_class = "uvicorn.workers.UvicornWorker"

# 允许转发的主机（重要：允许所有主机）
forwarded_allow_ips = "*"

# 代理允许来源（重要：允许所有来源）
proxy_allow_from = "*"

# 超时设置
timeout = 120
keepalive = 5

# 日志配置
accesslog = "-"
errorlog = "-"
loglevel = "info"

# 进程名称
proc_name = "intelliteam"

# 守护进程模式（后台运行）
daemon = False

# 重载配置（开发环境可设为 True）
reload = False

# 预加载应用
preload_app = True

# 最大请求数（防止内存泄漏）
max_requests = 1000
max_requests_jitter = 50
