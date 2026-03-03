# Docker Desktop 手动安装指南

## 方法 1: 自动安装脚本 (推荐)

以**管理员身份**运行 PowerShell，执行：

```powershell
cd F:\ai_agent
.\scripts\install-docker.ps1
```

脚本会自动：
1. 启用 WSL2 功能
2. 启用虚拟机平台
3. 下载 Docker Desktop
4. 静默安装

---

## 方法 2: 手动安装

### 步骤 1: 启用 WSL2

以**管理员身份**运行 PowerShell：

```powershell
# 启用 WSL 功能
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart

# 启用虚拟机平台
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart

# 重启电脑
shutdown /r /t 0
```

### 步骤 2: 安装 WSL2

重启后，运行：

```powershell
# 安装 WSL2
wsl --install

# 设置 WSL2 为默认版本
wsl --set-default-version 2
```

### 步骤 3: 下载 Docker Desktop

下载地址：https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe

或使用命令行：

```powershell
# 下载安装程序
Invoke-WebRequest -Uri "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe" -OutFile "$env:TEMP\DockerDesktopInstaller.exe"

# 运行安装
Start-Process "$env:TEMP\DockerDesktopInstaller.exe" -ArgumentList "install", "--quiet", "--noreboot"
```

### 步骤 4: 启动 Docker Desktop

1. 启动 Docker Desktop 应用
2. 登录 Docker Hub 账号（可免费注册）
3. 等待初始化完成

### 步骤 5: 验证安装

```powershell
# 检查版本
docker --version
docker compose version

# 测试运行
docker run hello-world
```

---

## 常见问题

### Q1: WSL2 安装失败

**错误**: "Virtualization is disabled"

**解决**: 
1. 重启电脑，进入 BIOS
2. 启用虚拟化技术 (Intel VT-x / AMD-V)
3. 保存并重启

### Q2: Docker Desktop 无法启动

**错误**: "WSL 2 installation is corrupt"

**解决**:
```powershell
# 更新 WSL
wsl --update

# 检查 WSL 版本
wsl --list --verbose

# 设置 WSL2
wsl --set-default-version 2
```

### Q3: Hyper-V 冲突

如果已安装 VMware/VirtualBox，可能与 Hyper-V 冲突。

**解决**:
1. 卸载 VMware/VirtualBox
2. 或使用 Docker Toolbox (不推荐)

---

## 安装后配置

### 启动 Redis

```bash
docker run -d --name intelliteam-redis -p 6379:6379 redis:7-alpine
```

### 启动完整服务

```bash
cd F:\ai_agent
docker-compose up -d
```

### 验证服务

```bash
# 检查容器
docker ps

# 测试 Redis
docker exec intelliteam-redis redis-cli ping
# 应返回：PONG

# 测试 API
curl http://localhost:8000/health
```

---

## 系统要求

- ✅ Windows 10 64-bit: Home 2009+ / Pro 1903+
- ✅ 虚拟化支持 (BIOS 中启用)
- ✅ 4GB RAM (推荐 8GB+)
- ✅ 50GB 可用磁盘空间

---

## 资源

- Docker Desktop 下载：https://www.docker.com/products/docker-desktop/
- WSL2 文档：https://docs.microsoft.com/windows/wsl/
- Docker 文档：https://docs.docker.com/

---

*最后更新：2026-03-03*
