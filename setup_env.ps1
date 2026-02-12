# ANK Backend - Environment Setup Script (PowerShell)
# Double-click this file or run: powershell -ExecutionPolicy Bypass -File setup_env.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ANK Backend - Environment Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Python is installed
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not installed or not in PATH!" -ForegroundColor Red
    Write-Host "Please install Python 3.8+ from https://www.python.org/downloads/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

# Check if virtual environment already exists
if (Test-Path "env\Scripts\Activate.ps1") {
    Write-Host "[WARNING] Virtual environment already exists in 'env' folder." -ForegroundColor Yellow
    $recreate = Read-Host "Do you want to recreate it? (Y/N)"
    if ($recreate -ne "Y" -and $recreate -ne "y") {
        Write-Host "Skipping virtual environment creation..." -ForegroundColor Yellow
    } else {
        Write-Host "Removing existing virtual environment..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force env
    }
}

# Create virtual environment
if (-not (Test-Path "env\Scripts\Activate.ps1")) {
    Write-Host "[2/5] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv env
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[ERROR] Failed to create virtual environment!" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    Write-Host "Virtual environment created successfully!" -ForegroundColor Green
    Write-Host ""
}

# Activate virtual environment
Write-Host "[3/5] Activating virtual environment..." -ForegroundColor Yellow
& "env\Scripts\Activate.ps1"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to activate virtual environment!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "Virtual environment activated!" -ForegroundColor Green
Write-Host ""

# Upgrade pip
Write-Host "[4/5] Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARNING] Failed to upgrade pip, continuing anyway..." -ForegroundColor Yellow
}
Write-Host ""

# Install requirements
Write-Host "[5/5] Installing requirements from requirements.txt..." -ForegroundColor Yellow
if (-not (Test-Path "requirements.txt")) {
    Write-Host "[ERROR] requirements.txt not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to install requirements!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Virtual environment is ready in the 'env' folder." -ForegroundColor Green
Write-Host ""
Write-Host "To activate it manually, run:" -ForegroundColor Yellow
Write-Host "  .\env\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To deactivate, run:" -ForegroundColor Yellow
Write-Host "  deactivate" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to exit"
