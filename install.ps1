# Yumi Installer for Windows (PowerShell)
# Usage: irm https://raw.githubusercontent.com/CodeNeuron58/Yumi/master/install.ps1 | iex

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  ________________________________________" -ForegroundColor Magenta
Write-Host "  |                                      |" -ForegroundColor Magenta
Write-Host "  |    Yumi  Installation Script        |" -ForegroundColor Magenta
Write-Host "  |    Real-Time AI Companion            |" -ForegroundColor Magenta
Write-Host "  |______________________________________|" -ForegroundColor Magenta
Write-Host ""

# Step 1: Check Python
Write-Host "[1/3] Checking Python version..." -ForegroundColor Cyan

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 12) {
                $pythonCmd = $cmd
                Write-Host "    Found $ver" -ForegroundColor Green
                break
            }
        }
    } catch { }
}

if (-not $pythonCmd) {
    Write-Host ""
    Write-Host "  ERROR: Python 3.12+ is required but not found." -ForegroundColor Red
    Write-Host "  Download from: https://python.org/downloads" -ForegroundColor Yellow
    Write-Host "  Make sure to check 'Add Python to PATH' during install." -ForegroundColor Yellow
    exit 1
}

# Step 2: Install uv if missing
Write-Host "[2/3] Checking uv package manager..." -ForegroundColor Cyan

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "    Installing uv..." -ForegroundColor Yellow
    try {
        irm https://astral.sh/uv/install.ps1 | iex
        $userPath = [System.Environment]::GetEnvironmentVariable("PATH", "User")
        $machinePath = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
        $env:PATH = "$userPath;$machinePath"
        Write-Host "    uv installed." -ForegroundColor Green
    } catch {
        Write-Host "  ERROR: Failed to install uv. Install it manually:" -ForegroundColor Red
        Write-Host "  https://docs.astral.sh/uv/getting-started/installation/" -ForegroundColor Yellow
        exit 1
    }
} else {
    $uvVer = uv --version 2>&1
    Write-Host "    Found $uvVer" -ForegroundColor Green
}

# Step 2.5: Ensure git is on PATH — the next step does `uv tool install git+https://...`
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "  ERROR: 'git' is required but not found on PATH." -ForegroundColor Red
    Write-Host "  Install Git for Windows: https://git-scm.com/download/win" -ForegroundColor Yellow
    Write-Host "  Then re-run this installer." -ForegroundColor Yellow
    exit 1
} else {
    $gitVer = git --version 2>&1
    Write-Host "    Found $gitVer" -ForegroundColor Green
}
# Step 3: Install Yumi
Write-Host "[3/3] Installing Yumi..." -ForegroundColor Cyan
Write-Host "    (Downloading dependencies, this may take a few minutes)" -ForegroundColor DarkGray

try {
    uv tool install git+https://github.com/CodeNeuron58/Yumi.git
} catch {
    Write-Host ""
    Write-Host "  ERROR: Installation failed." -ForegroundColor Red
    Write-Host "  Try manually: uv tool install git+https://github.com/CodeNeuron58/Yumi.git" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "  Yumi has been installed!" -ForegroundColor Green
Write-Host ""
Write-Host "  Run her with:" -ForegroundColor White
Write-Host "      yumi" -ForegroundColor Magenta
Write-Host ""
Write-Host "  GitHub: https://github.com/CodeNeuron58/Yumi" -ForegroundColor DarkGray
Write-Host ""
