# Makefile for IntelliTeam

.PHONY: help install test lint format build start stop restart clean deploy

# 默认目标
help:
	@echo "IntelliTeam 常用命令:"
	@echo ""
	@echo "  make install     - 安装依赖"
	@echo "  make test        - 运行测试"
	@echo "  make lint        - 代码检查"
	@echo "  make format      - 代码格式化"
	@echo "  make build       - 构建 Docker 镜像"
	@echo "  make start       - 启动服务"
	@echo "  make stop        - 停止服务"
	@echo "  make restart     - 重启服务"
	@echo "  make clean       - 清理缓存"
	@echo "  make deploy      - 生产部署"
	@echo ""

# 安装依赖
install:
	@echo "安装依赖..."
	pip install -r requirements.txt
	pip install black ruff mypy pre-commit
	@echo "依赖安装完成"

# 运行测试
test:
	@echo "运行测试..."
	python -m pytest tests/ -v --tb=short

# 运行测试并生成覆盖率报告
test-cov:
	@echo "运行测试并生成覆盖率报告..."
	python -m pytest tests/ --cov=src --cov-report=html --cov-report=term
	@echo "覆盖率报告：htmlcov/index.html"

# 代码检查
lint:
	@echo "代码检查..."
	ruff check src/ tests/
	mypy src/
	@echo "代码检查完成"

# 代码格式化
format:
	@echo "代码格式化..."
	black src/ tests/
	ruff check --fix src/ tests/
	@echo "代码格式化完成"

# 构建 Docker 镜像
build:
	@echo "构建 Docker 镜像..."
	docker-compose build
	@echo "构建完成"

# 启动服务
start:
	@echo "启动服务..."
	docker-compose up -d
	@echo "服务已启动"
	@echo "访问地址:"
	@echo "  - API: http://localhost:8000"
	@echo "  - Web UI: http://localhost:3000"
	@echo "  - Docs: http://localhost:8000/docs"

# 停止服务
stop:
	@echo "停止服务..."
	docker-compose down
	@echo "服务已停止"

# 重启服务
restart: stop start

# 清理缓存
clean:
	@echo "清理缓存..."
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf logs/
	rm -rf data/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	@echo "清理完成"

# 生产部署
deploy: lint test build start
	@echo "部署完成!"

# 开发模式启动
dev:
	@echo "开发模式启动..."
	python start.py --reload

# Web UI 启动
webui:
	@echo "启动 Web UI..."
	python webui/server.py

# 查看日志
logs:
	docker-compose logs -f

# 查看服务状态
status:
	docker-compose ps
	git status --short

# 初始化 Git
git-init:
	git init
	git add .
	git commit -m "Initial commit"

# 推送到 GitHub
git-push:
	git push -u origin main

# 创建新版本
version:
	@echo "当前版本:"
	git describe --tags --always --dirty
	@echo ""
	@echo "创建新版本:"
	@echo "  git tag v1.x.0"
	@echo "  git push origin v1.x.0"
