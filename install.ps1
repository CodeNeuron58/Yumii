# Yumii installer for Windows.
#
#   iex (irm https://yumii.me/install.ps1)
#
# What this does:
#   1. Installs uv (the Python package manager) if missing
#   2. uv installs its own Python 3.12 + the Yumii backend  (no
#      preinstalled Python needed)
#   3. Downloads the Yumii desktop app (a few MB)
#   4. Puts Yumii in your Start Menu
#
# Re-running this command updates everything.
# Uninstall: uv tool uninstall yumii; remove %LOCALAPPDATA%\Yumii and
# the Start Menu shortcut.

$ErrorActionPreference = "Stop"

$Repo = "CodeNeuron58/Yumi"
$AppDir = Join-Path $env:LOCALAPPDATA "Yumii"
$ExePath = Join-Path $AppDir "Yumii.exe"
$UvBin = Join-Path $env:USERPROFILE ".local\bin"

Write-Host ""
Write-Host "  Yumii - an AI companion for your desktop" -ForegroundColor Magenta
Write-Host "  ----------------------------------------" -ForegroundColor DarkGray
Write-Host ""

# -- 1/4: uv ----------------------------------------------------------------
Write-Host "[1/4] Package manager (uv)..." -ForegroundColor Cyan
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Host "      already installed." -ForegroundColor Green
} else {
    Write-Host "      installing uv..." -ForegroundColor DarkGray
    irm https://astral.sh/uv/install.ps1 | iex
    # Make uv visible to THIS session (the official installer updates the
    # user PATH, but only new terminals see that).
    $env:PATH = "$UvBin;$env:PATH"
    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        Write-Host ""
        Write-Host "  uv was installed but isn't on PATH yet." -ForegroundColor Red
        Write-Host "  Open a NEW terminal and run the install command again." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "      uv installed." -ForegroundColor Green
}

# -- 2/4: the Yumii backend (uv brings its own Python) ------------------------
Write-Host "[2/4] Yumii's brain (Python backend)..." -ForegroundColor Cyan
Write-Host "      (first install downloads a few hundred MB - one-time)" -ForegroundColor DarkGray
uv tool install --python 3.12 --upgrade yumii
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "  Backend install failed." -ForegroundColor Red
    Write-Host "  Try manually: uv tool install --python 3.12 yumii" -ForegroundColor Yellow
    exit 1
}
Write-Host "      backend ready." -ForegroundColor Green

# -- 3/4: the desktop app -----------------------------------------------------
Write-Host "[3/4] Yumii's desktop app..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
$exeUrl = "https://github.com/$Repo/releases/latest/download/Yumii.exe"
Invoke-WebRequest $exeUrl -OutFile $ExePath -UseBasicParsing
# The download carries the Mark-of-the-Web; you chose to install Yumii,
# so clear it for the app you just asked for.
Unblock-File $ExePath -ErrorAction SilentlyContinue
Write-Host "      installed to $AppDir" -ForegroundColor Green

# -- 4/4: Start Menu ----------------------------------------------------------
Write-Host "[4/4] Start Menu shortcut..." -ForegroundColor Cyan
$lnkPath = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Yumii.lnk"
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath = $ExePath
$lnk.WorkingDirectory = $AppDir
$lnk.Description = "Yumii - an AI companion for your desktop"
$lnk.Save()
Write-Host "      done." -ForegroundColor Green

Write-Host ""
Write-Host "  Yumii is installed!" -ForegroundColor Magenta
Write-Host ""
Write-Host "  Open the Start Menu and launch " -NoNewline
Write-Host "Yumii" -ForegroundColor Magenta -NoNewline
Write-Host "."
Write-Host "  (Her voice model downloads itself the first time she speaks.)" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  To update later: re-run this same command." -ForegroundColor DarkGray
Write-Host ""
