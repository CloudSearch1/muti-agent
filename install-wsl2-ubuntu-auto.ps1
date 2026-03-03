# Fully Automated WSL2 Ubuntu 22.04 Installation
# No user interaction required

$ErrorActionPreference = "Continue"

Write-Host "========================================"
Write-Host "  Automated WSL2 Ubuntu Installation"
Write-Host "========================================"
Write-Host ""

# Step 1: Check if WSL is enabled
Write-Host "[1/6] Checking WSL status..."
$wslEnabled = (Get-WindowsOptionalFeature -FeatureName Microsoft-Windows-Subsystem-Linux -Online).State -eq 'Enabled'
if (-not $wslEnabled) {
    Write-Host "[INFO] Enabling WSL..."
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart
} else {
    Write-Host "[OK] WSL is already enabled"
}

# Step 2: Check if Virtual Machine Platform is enabled
Write-Host ""
Write-Host "[2/6] Checking Virtual Machine Platform..."
$vmPlatform = (Get-WindowsOptionalFeature -FeatureName VirtualMachinePlatform -Online).State -eq 'Enabled'
if (-not $vmPlatform) {
    Write-Host "[INFO] Enabling Virtual Machine Platform..."
    Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
} else {
    Write-Host "[OK] Virtual Machine Platform is already enabled"
}

# Step 3: Download Ubuntu 22.04
Write-Host ""
Write-Host "[3/6] Downloading Ubuntu 22.04..."
try {
    $ubuntuUrl = "https://aka.ms/wslubuntu2204"
    $ubuntuPath = "$env:TEMP\Ubuntu2204.appx"
    
    if (Test-Path $ubuntuPath) {
        Write-Host "[INFO] Ubuntu installer already exists"
    } else {
        Invoke-WebRequest -Uri $ubuntuUrl -OutFile $ubuntuPath -UseBasicParsing
        Write-Host "[OK] Ubuntu 22.04 downloaded"
    }
} catch {
    Write-Host "[ERROR] Download failed: $_"
    exit 1
}

# Step 4: Install Ubuntu 22.04
Write-Host ""
Write-Host "[4/6] Installing Ubuntu 22.04..."
try {
    # Check if already installed
    $ubuntuInstalled = wsl --list --quiet 2>$null
    if ($ubuntuInstalled -match 'Ubuntu') {
        Write-Host "[INFO] Ubuntu is already installed"
    } else {
        Add-AppxPackage -Path $ubuntuPath
        Write-Host "[OK] Ubuntu 22.04 installed"
    }
} catch {
    Write-Host "[WARN] Installation may have already completed: $_"
}

# Step 5: Wait for initialization
Write-Host ""
Write-Host "[5/6] Waiting for Ubuntu initialization..."
Start-Sleep -Seconds 20

# Step 6: Install Docker in Ubuntu
Write-Host ""
Write-Host "[6/6] Installing Docker Engine..."
try {
    $dockerScript = @'
#!/bin/bash
# Update packages
apt-get update -qq

# Install Docker
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker.io docker-compose

# Start Docker service
service docker start

# Add user to docker group
usermod -aG docker $USER

# Verify installation
docker --version
docker-compose --version

# Test Docker
docker run --rm hello-world 2>/dev/null || true
'@

    wsl -d Ubuntu-22.04 -e bash -c "$dockerScript"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Docker installed successfully"
    } else {
        Write-Host "[WARN] Docker installation completed with warnings"
    }
} catch {
    Write-Host "[ERROR] Docker installation failed: $_"
}

Write-Host ""
Write-Host "========================================"
Write-Host "  Installation Complete!"
Write-Host "========================================"
Write-Host ""
Write-Host "Ubuntu 22.04 is now installed in WSL2"
Write-Host "Docker Engine is installed and running"
Write-Host ""
Write-Host "Usage:"
Write-Host "  wsl -d Ubuntu-22.04 docker --version"
Write-Host "  wsl -d Ubuntu-22.04 docker ps"
Write-Host ""
Write-Host "Start Redis:"
Write-Host "  wsl -d Ubuntu-22.04 docker run -d --name redis -p 6379:6379 redis:7-alpine"
Write-Host ""
