# WSL2 Docker Auto-Install Script

$ErrorActionPreference = "Stop"

Write-Host "========================================"
Write-Host "  WSL2 Docker Auto-Install"
Write-Host "========================================"
Write-Host ""

# Step 1: Download Ubuntu
Write-Host "[1/4] Downloading Ubuntu..."
try {
    $ubuntuUrl = "https://aka.ms/wslubuntu2204"
    $ubuntuPath = "$env:TEMP\Ubuntu.appx"
    
    Invoke-WebRequest -Uri $ubuntuUrl -OutFile $ubuntuPath -UseBasicParsing
    Write-Host "[OK] Ubuntu downloaded"
} catch {
    Write-Host "[ERROR] Ubuntu download failed: $_"
    exit 1
}

# Step 2: Install Ubuntu
Write-Host ""
Write-Host "[2/4] Installing Ubuntu..."
try {
    Add-AppxPackage -Path $ubuntuPath
    Write-Host "[OK] Ubuntu installed"
} catch {
    Write-Host "[WARN] Ubuntu may be already installed: $_"
}

# Step 3: Wait for initialization
Write-Host ""
Write-Host "[3/4] Waiting for Ubuntu initialization..."
Start-Sleep -Seconds 30

# Step 4: Install Docker
Write-Host ""
Write-Host "[4/4] Installing Docker Engine..."
try {
    wsl -d Ubuntu -e bash -c "
        apt-get update
        apt-get install -y docker.io docker-compose
        service docker start
        docker --version
    "
    Write-Host "[OK] Docker installed"
} catch {
    Write-Host "[ERROR] Docker install failed: $_"
    exit 1
}

Write-Host ""
Write-Host "========================================"
Write-Host "  Complete!"
Write-Host "========================================"
Write-Host ""
Write-Host "Docker is now installed in WSL2"
Write-Host ""
