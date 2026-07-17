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

$Repo    = "CodeNeuron58/Yumii"
$AppDir  = Join-Path $env:LOCALAPPDATA "Yumii"
$ExePath = Join-Path $AppDir "Yumii.exe"

# Pull the PATH the uv installer just wrote (it edits the *User* PATH,
# which only new terminals normally see) into this session.
function Update-SessionPath {
    $machine = [System.Environment]::GetEnvironmentVariable("PATH", "Machine")
    $user    = [System.Environment]::GetEnvironmentVariable("PATH", "User")
    $env:PATH = "$machine;$user"
}

# Resolve the PowerShell host exe to use when spawning child processes.
# We must NOT hardcode "powershell" because under PowerShell 7+ (pwsh),
# the classic powershell.exe may not be on PATH, causing:
#   "The term 'powershell' is not recognized"
# Strategy: prefer the absolute path of the host we're already running in,
# then fall back to whichever of powershell/pwsh is findable on PATH.
function Get-PowerShellHostExe {
    try {
        $hostExe = (Get-Process -Id $PID).Path
        if ($hostExe -and (Test-Path $hostExe)) {
            $leaf = Split-Path $hostExe -Leaf
            # Only trust a real PowerShell CLI, not ISE or an embedded host.
            if ($leaf -match '^(?i:powershell|pwsh)\.exe$') { return $hostExe }
        }
    } catch { }
    foreach ($candidate in @("powershell", "pwsh")) {
        $cmd = Get-Command $candidate -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($cmd -and $cmd.Source) { return $cmd.Source }
    }
    # Last resort: bare name so the spawn at least surfaces its own error.
    return "powershell"
}

# Locate uv by full path so nothing depends on PATH being refreshed.
function Find-Uv {
    $cmd = Get-Command uv -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($p in @(
        (Join-Path $env:USERPROFILE ".local\bin\uv.exe"),
        (Join-Path $env:USERPROFILE ".cargo\bin\uv.exe")
    )) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

# The whole install runs inside try/catch so a failure prints a readable
# message and LEAVES THE WINDOW OPEN. (The old script called `exit`,
# which closes the PowerShell window when run via `iex (irm ...)` — so
# any error vanished before you could read it.)
try {
    Write-Host ""
    Write-Host "  Yumii - an AI companion for your desktop" -ForegroundColor Magenta
    Write-Host "  ----------------------------------------" -ForegroundColor DarkGray
    Write-Host ""

    # -- 1/4: uv --------------------------------------------------------------
    Write-Host "[1/4] Package manager (uv)..." -ForegroundColor Cyan
    $uv = Find-Uv
    if ($uv) {
        Write-Host "      already installed." -ForegroundColor Green
    } else {
        Write-Host "      installing uv..." -ForegroundColor DarkGray
        $psHostExe = Get-PowerShellHostExe
        & $psHostExe -ExecutionPolicy Bypass -NoProfile -c "irm https://astral.sh/uv/install.ps1 | iex"
        Update-SessionPath
        $uv = Find-Uv
        if (-not $uv) {
            throw "uv was installed but couldn't be located. Close this window, open a NEW PowerShell, and run the command again."
        }
        Write-Host "      uv installed." -ForegroundColor Green
    }

    # -- 2/4: the Yumii backend (uv brings its own Python) --------------------
    Write-Host "[2/4] Yumii's brain (Python backend)..." -ForegroundColor Cyan
    Write-Host "      (first install downloads a few hundred MB - one-time)" -ForegroundColor DarkGray
    & $uv tool install --python 3.12 --upgrade yumii
    if ($LASTEXITCODE -ne 0) {
        throw "Backend install failed. Try manually: uv tool install --python 3.12 yumii"
    }
    Write-Host "      backend ready." -ForegroundColor Green

    # -- 3/4: the desktop app -------------------------------------------------
    Write-Host "[3/4] Yumii's desktop app..." -ForegroundColor Cyan
    New-Item -ItemType Directory -Force -Path $AppDir | Out-Null
    $exeUrl = "https://github.com/$Repo/releases/latest/download/Yumii.exe"
    Invoke-WebRequest $exeUrl -OutFile $ExePath -UseBasicParsing
    # The download carries the Mark-of-the-Web; you chose to install Yumii,
    # so clear it for the app you just asked for.
    Unblock-File $ExePath -ErrorAction SilentlyContinue
    Write-Host "      installed to $AppDir" -ForegroundColor Green

    # -- 4/4: Start Menu ------------------------------------------------------
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
}
catch {
    Write-Host ""
    Write-Host "  Install hit a snag:" -ForegroundColor Red
    Write-Host "  $($_.Exception.Message)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Nothing on your system was left broken. You can re-run the" -ForegroundColor DarkGray
    Write-Host "  command, or report this at https://github.com/$Repo/issues" -ForegroundColor DarkGray
    Write-Host ""
}
