# Docker Desktop 自动安装脚本

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Docker Desktop 自动安装脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] "Administrator")
if (-not $isAdmin) {
    Write-Host "ERROR: Administrator privileges required" -ForegroundColor Red
    Write-Host "Please right-click and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

Write-Host "[OK] Administrator privileges check passed" -ForegroundColor Green
Write-Host ""

# 步骤 1: 启用 WSL2 功能
Write-Host "[1/4] Enabling WSL2 feature..." -ForegroundColor Yellow
try {
    dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
    Write-Host "[OK] WSL2 feature enabled" -ForegroundColor Green
} catch {
    Write-Host "ERROR: WSL2 feature enable failed: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# 步骤 2: 启用虚拟机平台功能
Write-Host "[2/4] Enabling Virtual Machine Platform..." -ForegroundColor Yellow
try {
    dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
    Write-Host "[OK] Virtual Machine Platform enabled" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Virtual Machine Platform enable failed: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

# 步骤 3: 下载并安装 Docker Desktop
Write-Host "[3/4] Downloading Docker Desktop..." -ForegroundColor Yellow
$dockerInstallerUrl = "https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
$dockerInstallerPath = "$env:TEMP\DockerDesktopInstaller.exe"

try {
    Invoke-WebRequest -Uri $dockerInstallerUrl -OutFile $dockerInstallerPath -UseBasicParsing
    Write-Host "[OK] Docker Desktop downloaded" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Docker Desktop download failed: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "[4/4] Installing Docker Desktop..." -ForegroundColor Yellow
try {
    Start-Process -FilePath $dockerInstallerPath -ArgumentList "install", "--quiet", "--noreboot" -Wait
    Write-Host "[OK] Docker Desktop installed" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Docker Desktop install failed: $_" -ForegroundColor Red
    exit 1
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Green
Write-Host "SUCCESS: Docker Desktop installation complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "IMPORTANT:" -ForegroundColor Yellow
Write-Host "1. Please RESTART your computer" -ForegroundColor White
Write-Host "2. After restart, launch Docker Desktop" -ForegroundColor White
Write-Host "3. First launch requires Docker Hub login (free account)" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Restart computer" -ForegroundColor White
Write-Host "2. Run: docker --version" -ForegroundColor White
Write-Host "3. Run: docker run hello-world" -ForegroundColor White
Write-Host ""

# 询问是否重启
$restart = Read-Host "Restart computer now? (y/n)"
if ($restart -eq "y") {
    Write-Host "Restarting..." -ForegroundColor Yellow
    Restart-Computer -Force
}
