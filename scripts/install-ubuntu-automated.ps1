# WSL2 Ubuntu 自动化安装脚本
# 用途：自动安装 Ubuntu 22.04 到 WSL2

$ErrorActionPreference = "Continue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  WSL2 Ubuntu 自动化安装脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 步骤 1: 检查 WSL 是否已启用
Write-Host "[1/8] 检查 WSL 状态..." -ForegroundColor Yellow
try {
    $wslStatus = wsl --status 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] WSL 已启用" -ForegroundColor Green
    } else {
        Write-Host "[INFO] 启用 WSL 功能..." -ForegroundColor Yellow
        Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart
    }
} catch {
    Write-Host "[ERROR] WSL 检查失败：$_" -ForegroundColor Red
    exit 1
}

# 步骤 2: 检查虚拟机平台
Write-Host ""
Write-Host "[2/8] 检查虚拟机平台..." -ForegroundColor Yellow
try {
    $vmStatus = (Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform).State
    if ($vmStatus -eq 'Enabled') {
        Write-Host "[OK] 虚拟机平台已启用" -ForegroundColor Green
    } else {
        Write-Host "[INFO] 启用虚拟机平台..." -ForegroundColor Yellow
        Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
        Write-Host "[WARN] 需要重启电脑，请重启后重新运行此脚本" -ForegroundColor Yellow
        exit 0
    }
} catch {
    Write-Host "[ERROR] 虚拟机平台检查失败：$_" -ForegroundColor Red
    exit 1
}

# 步骤 3: 设置 WSL 默认版本为 2
Write-Host ""
Write-Host "[3/8] 设置 WSL 默认版本..." -ForegroundColor Yellow
try {
    wsl --set-default-version 2
    Write-Host "[OK] WSL 默认版本设置为 2" -ForegroundColor Green
} catch {
    Write-Host "[WARN] WSL 版本设置可能已存在：$_" -ForegroundColor Yellow
}

# 步骤 4: 下载 Ubuntu 22.04
Write-Host ""
Write-Host "[4/8] 下载 Ubuntu 22.04..." -ForegroundColor Yellow
$ubuntuUrl = "https://aka.ms/wslubuntu2204"
$ubuntuPath = "$env:TEMP\Ubuntu2204.appx"

if (Test-Path $ubuntuPath) {
    Write-Host "[INFO] Ubuntu 安装包已存在，跳过下载" -ForegroundColor Green
} else {
    Write-Host "  下载地址：$ubuntuUrl"
    Write-Host "  保存路径：$ubuntuPath"
    
    try {
        # 显示下载进度
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $ubuntuUrl -OutFile $ubuntuPath -UseBasicParsing
        
        if (Test-Path $ubuntuPath) {
            $size = (Get-Item $ubuntuPath).Length / 1MB
            Write-Host "[OK] Ubuntu 下载完成 (大小：$([math]::Round($size, 2)) MB)" -ForegroundColor Green
        } else {
            Write-Host "[ERROR] 下载失败" -ForegroundColor Red
            exit 1
        }
    } catch {
        Write-Host "[ERROR] 下载失败：$_" -ForegroundColor Red
        exit 1
    }
}

# 步骤 5: 安装 Ubuntu 应用包
Write-Host ""
Write-Host "[5/8] 安装 Ubuntu 应用包..." -ForegroundColor Yellow
try {
    Add-AppxPackage -Path $ubuntuPath
    Write-Host "[OK] Ubuntu 应用包安装完成" -ForegroundColor Green
} catch {
    if ($_.Exception.Message -like "*already installed*") {
        Write-Host "[INFO] Ubuntu 已经安装" -ForegroundColor Green
    } else {
        Write-Host "[ERROR] 安装失败：$_" -ForegroundColor Red
        exit 1
    }
}

# 步骤 6: 验证 Ubuntu 安装
Write-Host ""
Write-Host "[6/8] 验证 Ubuntu 安装..." -ForegroundColor Yellow
try {
    $wslList = wsl --list --verbose 2>&1
    if ($wslList -match 'Ubuntu') {
        Write-Host "[OK] Ubuntu 已安装" -ForegroundColor Green
        Write-Host ""
        Write-Host "WSL 发行版列表:" -ForegroundColor Cyan
        Write-Host $wslList
    } else {
        Write-Host "[WARN] Ubuntu 可能正在初始化..." -ForegroundColor Yellow
    }
} catch {
    Write-Host "[WARN] 验证失败：$_" -ForegroundColor Yellow
}

# 步骤 7: 初始化 Ubuntu
Write-Host ""
Write-Host "[7/8] 初始化 Ubuntu..." -ForegroundColor Yellow
Write-Host "[INFO] 首次启动需要配置用户名和密码" -ForegroundColor Cyan
Write-Host ""

try {
    # 尝试启动 Ubuntu（会提示用户设置）
    Write-Host "准备启动 Ubuntu 进行初始化..." -ForegroundColor Yellow
    Write-Host "按任意键启动 Ubuntu 初始化..." -ForegroundColor Cyan
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    
    # 启动 Ubuntu
    wsl -d Ubuntu
    
    Write-Host "[OK] Ubuntu 初始化完成" -ForegroundColor Green
} catch {
    Write-Host "[WARN] 初始化可能需要手动完成：$_" -ForegroundColor Yellow
}

# 步骤 8: 安装 Docker（可选）
Write-Host ""
Write-Host "[8/8] 是否安装 Docker？" -ForegroundColor Yellow
$response = Read-Host "输入 Y 安装 Docker，或按 Enter 跳过"

if ($response -eq 'Y' -or $response -eq 'y') {
    Write-Host ""
    Write-Host "正在安装 Docker..." -ForegroundColor Yellow
    
    try {
        wsl -d Ubuntu -e bash -c "
            apt-get update -qq
            DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io
            service docker start
            docker --version
        "
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Docker 安装完成" -ForegroundColor Green
        } else {
            Write-Host "[WARN] Docker 安装失败，可以稍后手动安装" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[ERROR] Docker 安装失败：$_" -ForegroundColor Red
    }
}

# 完成
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  安装完成！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "后续步骤:" -ForegroundColor Cyan
Write-Host "  1. 验证安装：wsl --list --verbose" -ForegroundColor White
Write-Host "  2. 启动 Ubuntu: wsl -d Ubuntu" -ForegroundColor White
Write-Host "  3. 安装 Docker: wsl -d Ubuntu -e bash -c 'apt-get install -y docker.io'" -ForegroundColor White
Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Cyan
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
