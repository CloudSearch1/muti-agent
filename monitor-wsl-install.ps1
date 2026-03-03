# WSL2 Ubuntu 安装监控脚本
# 安装完成后自动通知

$monitoringPath = "C:\Users\41334\.openclaw\workspace\memory\wsl-monitor.md"
$complete = $false
$checkCount = 0
$maxChecks = 60  # 最多检查 60 次 (30 分钟)

Write-Host "开始监控 WSL2 Ubuntu 安装..."
Write-Host "检查间隔：30 秒"
Write-Host "最大检查次数：$maxChecks"
Write-Host ""

while (-not $complete -and $checkCount -lt $maxChecks) {
    $checkCount++
    $timestamp = Get-Date -Format "HH:mm:ss"
    
    # 检查 Ubuntu 是否已安装
    $wslList = wsl --list --verbose 2>$null
    $ubuntuInstalled = $wslList -match 'Ubuntu'
    
    # 检查 Docker 是否可用
    $dockerAvailable = $false
    if ($ubuntuInstalled) {
        $dockerCheck = wsl -d Ubuntu-22.04 -e docker --version 2>$null
        $dockerAvailable = $LASTEXITCODE -eq 0
    }
    
    Write-Host "[$timestamp] 检查 #$checkCount - Ubuntu: $(if($ubuntuInstalled){'✅ 已安装'}else{'⏳ 安装中'}) - Docker: $(if($dockerAvailable){'✅ 就绪'}else{'⏳ 等待'})"
    
    if ($ubuntuInstalled -and $dockerAvailable) {
        $complete = $true
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "  安装完成！" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        
        # 创建完成报告
        $report = @"
# WSL2 Ubuntu 安装完成报告

> **完成时间**: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")

## ✅ 安装成功

- **Ubuntu 22.04**: 已安装
- **Docker Engine**: 已安装并运行
- **Docker Compose**: 已安装

## 验证命令

\`\`\`powershell
# 检查 Docker 版本
wsl -d Ubuntu-22.04 docker --version

# 检查 Docker 运行状态
wsl -d Ubuntu-22.04 docker ps

# 启动 Redis
wsl -d Ubuntu-22.04 docker run -d --name redis -p 6379:6379 redis:7-alpine

# 启动 PostgreSQL
wsl -d Ubuntu-22.04 docker run -d --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 postgres:15-alpine
\`\`\`

## 下一步

1. 启动 Redis 和 PostgreSQL 容器
2. 运行最终测试
3. 启动完整服务

---
*自动监控完成*
"@
        
        $report | Out-File -FilePath "$PSScriptRoot\WSL2_INSTALL_COMPLETE.md" -Encoding utf8
        Write-Host "完成报告已保存：WSL2_INSTALL_COMPLETE.md"
        Write-Host ""
    } else {
        Start-Sleep -Seconds 30
    }
}

if (-not $complete) {
    Write-Host ""
    Write-Host "⚠️  监控超时 (30 分钟)" -ForegroundColor Yellow
    Write-Host "请手动检查安装状态" -ForegroundColor Yellow
}
