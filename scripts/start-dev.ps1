<#
.SYNOPSIS
    One-Click OmniBench Development Launcher for Windows 11 (PowerShell).
.DESCRIPTION
    Automates prerequisite checking, virtual environment setup, package installation,
    benchmark data ingestion & dataset building, and launches the Vite dev server.
#>

[CmdletBinding()]
param(
    [switch]$SkipIngest = $false,
    [switch]$Docker = $false
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  OmniBench — Windows 11 Development Launcher" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Option: Run via Docker Compose
if ($Docker) {
    Write-Host "[*] Launching via Docker Desktop container..." -ForegroundColor Yellow
    if (-not (Get-Command "docker" -ErrorAction SilentlyContinue)) {
        Write-Error "Docker is not installed or not in PATH. Install Docker Desktop or run without -Docker."
    }
    docker compose up -d
    Write-Host "[+] Docker container running! Attaching interactive bash shell..." -ForegroundColor Green
    docker exec -it omnibench-dev bash
    exit 0
}

# 2. Check Prerequisites
Write-Host "[1/5] Checking Windows 11 prerequisites..." -ForegroundColor Cyan

$pythonCmd = $null
if (Get-Command "py" -ErrorAction SilentlyContinue) {
    $pythonCmd = "py -3.12"
} elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    $pythonCmd = "python"
} else {
    Write-Error "Python 3.12 is not found in PATH. Install via: winget install Python.Python.3.12"
}

if (-not (Get-Command "node" -ErrorAction SilentlyContinue)) {
    Write-Error "Node.js is not found in PATH. Install via: winget install OpenJS.NodeJS.LTS"
}
if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    Write-Error "npm is not found in PATH."
}

Write-Host "      Python: OK ($pythonCmd)" -ForegroundColor Green
Write-Host "      Node.js: OK ($(node --version))" -ForegroundColor Green
Write-Host "      npm:     OK ($(npm --version))" -ForegroundColor Green

# 3. Python Virtual Environment Setup
Write-Host "`n[2/5] Setting up Python virtual environment (.venv)..." -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    Write-Host "      Creating .venv..." -ForegroundColor Gray
    Invoke-Expression "$pythonCmd -m venv .venv"
}

$venvPython = ".\.venv\Scripts\python.exe"
$venvPip = ".\.venv\Scripts\pip.exe"

if (-not (Test-Path $venvPython)) {
    Write-Error "Virtual environment python executable not found at $venvPython."
}

Write-Host "      Installing Python requirements..." -ForegroundColor Gray
& $venvPip install --quiet -r requirements.txt

# 4. Data Ingestion & Build Dataset
if (-not $SkipIngest) {
    Write-Host "`n[3/5] Refreshing and normalizing benchmark data..." -ForegroundColor Cyan
    & $venvPython -m scripts.ingest.run_all
    & $venvPython -m scripts.transform.build_dataset
    & $venvPython -m scripts.ci.archive_snapshot
} else {
    Write-Host "`n[3/5] Skipping benchmark ingestion (-SkipIngest active)..." -ForegroundColor Yellow
}

# 5. Node / Frontend Dependencies
Write-Host "`n[4/5] Checking Node dependencies..." -ForegroundColor Cyan
if (-not (Test-Path "node_modules")) {
    Write-Host "      Installing npm packages (npm install)..." -ForegroundColor Gray
    npm install
} else {
    Write-Host "      node_modules already present." -ForegroundColor Green
}

# 6. Launch Vite Dev Server
Write-Host "`n[5/5] Starting Vite development server..." -ForegroundColor Cyan
Write-Host "      OmniBench dashboard will be available at: http://localhost:5173/" -ForegroundColor Green
Write-Host "      Press Ctrl+C to stop the development server.`n" -ForegroundColor Gray

# Open default Windows 11 browser after 2 seconds
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 2
    Start-Process "http://localhost:5173/"
} | Out-Null

npm run dev
