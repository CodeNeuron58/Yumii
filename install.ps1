# Yumii installer for Windows.
#
#   iex (irm https://yumii.me/install.ps1)
#
# What this does:
#   0. Onboards you: picks your mind / ears / voice + API keys (2 min,
#      arrow keys or numbers) and saves them -- so the app downloads ONLY
#      the models you actually chose
#   1. Installs uv (the Python package manager) if missing
#   2. uv installs its own Python 3.12 + the Yumii backend  (no
#      preinstalled Python needed)
#   3. Downloads the Yumii desktop app (a few MB)
#   4. Puts Yumii in your Start Menu
#
# Re-running this command updates everything -- and keeps your existing
# settings (delete ~/.yumii/config.json to redo onboarding).
# Uninstall: uv tool uninstall yumii; remove %LOCALAPPDATA%\Yumii and
# the Start Menu shortcut.

$ErrorActionPreference = "Stop"

$Repo    = "CodeNeuron58/Yumii"
$AppDir  = Join-Path $env:LOCALAPPDATA "Yumii"
$ExePath = Join-Path $AppDir "Yumii.exe"
$YumiiDir = Join-Path $env:USERPROFILE ".yumii"

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

# -- Onboarding UI ---------------------------------------------------------

function Write-YumiiBanner {
    # The art is built from code points at runtime so THIS FILE stays pure
    # ASCII: PowerShell 5.1 decodes BOM-less text as ANSI, and half of these
    # box-drawing characters contain a byte that decodes to a curly quote --
    # which would shatter the strings at iex (irm ...) time.
    $bannerLines = @(
        @(0x2588, 0x2588, 0x2557, 0x0020, 0x0020, 0x0020, 0x2588, 0x2588, 0x2557, 0x2588, 0x2588, 0x2557, 0x0020, 0x0020, 0x0020, 0x2588, 0x2588, 0x2557, 0x2588, 0x2588, 0x2588, 0x2557, 0x0020, 0x0020, 0x0020, 0x2588, 0x2588, 0x2588, 0x2557, 0x2588, 0x2588, 0x2557, 0x0020, 0x2588, 0x2588, 0x2557),
        @(0x255A, 0x2588, 0x2588, 0x2557, 0x0020, 0x2588, 0x2588, 0x2554, 0x255D, 0x2588, 0x2588, 0x2551, 0x0020, 0x0020, 0x0020, 0x2588, 0x2588, 0x2551, 0x2588, 0x2588, 0x2588, 0x2588, 0x2557, 0x0020, 0x2588, 0x2588, 0x2588, 0x2588, 0x2551, 0x2588, 0x2588, 0x2551, 0x0020, 0x2588, 0x2588, 0x2551),
        @(0x0020, 0x255A, 0x2588, 0x2588, 0x2588, 0x2588, 0x2554, 0x255D, 0x0020, 0x2588, 0x2588, 0x2551, 0x0020, 0x0020, 0x0020, 0x2588, 0x2588, 0x2551, 0x2588, 0x2588, 0x2554, 0x2588, 0x2588, 0x2588, 0x2588, 0x2554, 0x2588, 0x2588, 0x2551, 0x2588, 0x2588, 0x2551, 0x0020, 0x2588, 0x2588, 0x2551),
        @(0x0020, 0x0020, 0x255A, 0x2588, 0x2588, 0x2554, 0x255D, 0x0020, 0x0020, 0x2588, 0x2588, 0x2551, 0x0020, 0x0020, 0x0020, 0x2588, 0x2588, 0x2551, 0x2588, 0x2588, 0x2551, 0x255A, 0x2588, 0x2588, 0x2554, 0x255D, 0x2588, 0x2588, 0x2551, 0x2588, 0x2588, 0x2551, 0x0020, 0x2588, 0x2588, 0x2551),
        @(0x0020, 0x0020, 0x0020, 0x2588, 0x2588, 0x2551, 0x0020, 0x0020, 0x0020, 0x255A, 0x2588, 0x2588, 0x2588, 0x2588, 0x2588, 0x2588, 0x2554, 0x255D, 0x2588, 0x2588, 0x2551, 0x0020, 0x255A, 0x2550, 0x255D, 0x0020, 0x2588, 0x2588, 0x2551, 0x2588, 0x2588, 0x2551, 0x0020, 0x2588, 0x2588, 0x2551),
        @(0x0020, 0x0020, 0x0020, 0x255A, 0x2550, 0x255D, 0x0020, 0x0020, 0x0020, 0x0020, 0x255A, 0x2550, 0x2550, 0x2550, 0x2550, 0x2550, 0x255D, 0x0020, 0x255A, 0x2550, 0x255D, 0x0020, 0x0020, 0x0020, 0x0020, 0x0020, 0x255A, 0x2550, 0x255D, 0x255A, 0x2550, 0x255D, 0x0020, 0x255A, 0x2550, 0x255D)
    )
    $colors = @("DarkCyan", "DarkCyan", "Cyan", "Cyan", "Green", "Green")
    Write-Host ""
    for ($i = 0; $i -lt $bannerLines.Count; $i++) {
        $text = -join ($bannerLines[$i] | ForEach-Object { [char]$_ })
        Write-Host "  $text" -ForegroundColor $colors[$i]
    }
    Write-Host ""
    Write-Host "     the AI companion that's actually yours." -ForegroundColor White
    Write-Host ""
}

# Arrow-key menu (numbers fallback when the console can't do ReadKey --
# e.g. redirected input). Returns the chosen INDEX.
function Show-Menu {
    param([string]$Title, [string[]]$Options, [string]$Hint = "")

    Write-Host ""
    Write-Host "  $Title" -ForegroundColor White
    if ($Hint) { Write-Host "  $Hint" -ForegroundColor DarkGray }

    $sel = 0
    try {
        [Console]::CursorVisible = $false
        $top = [Console]::CursorTop
        $width = [Math]::Max(40, [Console]::WindowWidth - 2)
        while ($true) {
            for ($i = 0; $i -lt $Options.Count; $i++) {
                $mark = if ($i -eq $sel) { "  > " } else { "    " }
                $color = if ($i -eq $sel) { "Green" } else { "Gray" }
                [Console]::SetCursorPosition(0, $top + $i)
                Write-Host ("$mark$($Options[$i])  ").PadRight($width) -ForegroundColor $color
            }
            $key = [Console]::ReadKey($true)
            if ($key.Key -eq "UpArrow")   { $sel = ($sel - 1 + $Options.Count) % $Options.Count }
            if ($key.Key -eq "DownArrow") { $sel = ($sel + 1) % $Options.Count }
            if ($key.Key -in @("Enter", "Spacebar")) { break }
        }
        [Console]::SetCursorPosition(0, $top + $Options.Count)
        [Console]::CursorVisible = $true
    } catch {
        [Console]::CursorVisible = $true
        for ($i = 0; $i -lt $Options.Count; $i++) {
            Write-Host "  [$($i + 1)] $($Options[$i])"
        }
        while ($true) {
            $pick = Read-Host "  Choose 1-$($Options.Count)"
            if ($pick -match '^\d+$' -and [int]$pick -ge 1 -and [int]$pick -le $Options.Count) {
                $sel = [int]$pick - 1
                break
            }
        }
    }
    Write-Host "  chosen: $($Options[$sel])" -ForegroundColor Green
    return $sel
}

function Read-Secret {
    param([string]$Prompt)
    while ($true) {
        $sec = Read-Host "  $Prompt" -AsSecureString
        $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
        try {
            $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
        if ($key.Trim()) { return $key.Trim() }
        Write-Host "  (that was empty -- paste the key)" -ForegroundColor Yellow
    }
}

# Merge written choices into ~/.yumii WITHOUT BOM -- the Python backend
# reads these files as utf-8 and PowerShell 5.1's `-Encoding UTF8` adds a
# BOM that json.load rejects (the whole config would be silently dropped).
function ConvertTo-HashtableLoose($obj) {
    $h = @{}
    if ($obj -is [hashtable]) { foreach ($k in $obj.Keys) { $h[$k] = $obj[$k] } }
    elseif ($null -ne $obj) { foreach ($p in $obj.PSObject.Properties) { $h[$p.Name] = $p.Value } }
    return $h
}

function Write-NoBomJson {
    param([string]$Path, [hashtable]$Data)
    $json = $Data | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($Path, $json, (New-Object System.Text.UTF8Encoding($false)))
}

function Save-Onboarding {
    param([hashtable]$Preferences, [hashtable]$Credentials)
    New-Item -ItemType Directory -Force -Path $YumiiDir | Out-Null

    $cfgPath = Join-Path $YumiiDir "config.json"
    $config = ConvertTo-HashtableLoose $null
    if (Test-Path $cfgPath) {
        try { $config = ConvertTo-HashtableLoose (Get-Content $cfgPath -Raw | ConvertFrom-Json) } catch { $config = @{} }
    }
    foreach ($k in $Preferences.Keys) { $config[$k] = $Preferences[$k] }
    Write-NoBomJson -Path $cfgPath -Data $config

    if ($Credentials.Count -gt 0) {
        $authPath = Join-Path $YumiiDir "auth.json"
        $auth = @{}
        if (Test-Path $authPath) {
            try { $auth = ConvertTo-HashtableLoose (Get-Content $authPath -Raw | ConvertFrom-Json) } catch { $auth = @{} }
        }
        foreach ($k in $Credentials.Keys) { $auth[$k] = $Credentials[$k] }
        Write-NoBomJson -Path $authPath -Data $auth
    }
}

# The onboarding itself. Skipped on updates (existing config wins).
# Returns $true when fresh onboarding ran (so the summary can say what
# downloads on first launch), $false when settings were kept.
function Start-Onboarding {
    # Updating? Keep the user's settings -- this command doubles as update.
    if (Test-Path (Join-Path $YumiiDir "config.json")) {
        Write-Host "  Existing Yumii settings found -- keeping them." -ForegroundColor Green
        Write-Host "  (Delete ~/.yumii/config.json and re-run to redo this setup.)" -ForegroundColor DarkGray
        return $false
    }

    Write-Host "  Let's set her up. Arrow keys + Enter (or type a number)." -ForegroundColor DarkGray

    # -- Mind --------------------------------------------------------------
    $mindIdx = Show-Menu -Title "Her mind (the AI she thinks with)" -Options @(
        "NVIDIA Nemotron on Nebius Token Factory (recommended)"
        "Groq (free tier)"
        "Ollama Cloud"
        "Google Gemini"
        "OpenAI"
        "Anthropic"
        "OpenRouter"
        "Choose later in the app"
    ) -Hint "You can change this any time in the dashboard."

    $mindIds    = @("nebius", "groq", "ollama", "google", "openai", "anthropic", "openrouter", $null)
    $mindKeys   = @("NEBIUS_API_KEY", "GROQ_API_KEY", "OLLAMA_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", $null)
    $mind = $mindIds[$mindIdx]
    $mindKeyName = $mindKeys[$mindIdx]

    $prefs = @{}
    $creds = @{}
    if ($mind) {
        $prefs["LLM_PROVIDER"] = $mind
        if ($mind -eq "nebius") {
            Write-Host "  Get a key at https://tokenfactory.nebius.com/project/api-keys" -ForegroundColor DarkGray
        }
        $key = Read-Secret -Prompt "Paste your $mind API key"
        $creds[$mindKeyName] = $key
        if ($mind -notin @("nebius", "groq", "ollama")) {
            Write-Host "  (You'll pick the exact model in Yumii's dashboard on first launch.)" -ForegroundColor DarkGray
        }
    }

    # -- Ears --------------------------------------------------------------
    $earIdx = Show-Menu -Title "Her ears (speech-to-text)" -Options @(
        "Local Whisper (private, offline -- recommended)"
        "Groq Whisper (cloud, fast)"
        "Vosk (offline streaming, lightest)"
    ) -Hint "Local downloads a model here; cloud downloads nothing."
    $ears = @("local", "groq", "vosk")[$earIdx]
    $prefs["STT_PROVIDER"] = $ears

    if ($ears -eq "local") {
        $sizeIdx = Show-Menu -Title "Whisper model size" -Options @(
            "base (recommended)"
            "tiny (lightest, fastest)"
            "small (most accurate, bigger download)"
        )
        $prefs["WHISPER_MODEL_SIZE"] = @("base", "tiny", "small")[$sizeIdx]
    }
    if ($ears -eq "groq" -and -not $creds.ContainsKey("GROQ_API_KEY")) {
        $creds["GROQ_API_KEY"] = Read-Secret -Prompt "Paste your Groq API key (used for her ears)"
    }

    # -- Voice -------------------------------------------------------------
    $voiceIdx = Show-Menu -Title "Her voice (text-to-speech)" -Options @(
        "Kokoro (local, free -- recommended)"
        "ElevenLabs (cloud)"
        "CAMB.ai (cloud)"
    ) -Hint "Local downloads her voice here; cloud downloads nothing."
    $voice = @("Kokoro", "ElevenLabs", "CAMB.ai")[$voiceIdx]
    $prefs["TTS_PROVIDER"] = $voice

    if ($voice -eq "ElevenLabs") {
        $creds["ELEVENLABS_API_KEY"]  = Read-Secret -Prompt "Paste your ElevenLabs API key"
        $creds["ELEVENLABS_VOICE_ID"] = Read-Secret -Prompt "Paste your ElevenLabs Voice ID"
    }
    if ($voice -eq "CAMB.ai") {
        $creds["CAMB_API_KEY"]  = Read-Secret -Prompt "Paste your CAMB.ai API key"
        $creds["CAMB_VOICE_ID"] = Read-Secret -Prompt "Paste your CAMB.ai Voice ID"
    }

    Save-Onboarding -Preferences $prefs -Credentials $creds

    # -- Tell them exactly what downloads on first launch -------------------
    Write-Host ""
    Write-Host "  On first launch she downloads only what you picked:" -ForegroundColor DarkGray
    if ($ears -eq "local") { Write-Host "    - Whisper $($prefs['WHISPER_MODEL_SIZE']) (~150-500 MB, her ears)" -ForegroundColor DarkGray }
    if ($voice -eq "Kokoro") { Write-Host "    - Kokoro voice (~325 MB, her voice)" -ForegroundColor DarkGray }
    if ($ears -ne "local" -and $voice -ne "Kokoro") {
        Write-Host "    - nothing big: cloud ears and voice download nothing" -ForegroundColor DarkGray
    }
    return $true
}

# The whole install runs inside try/catch so a failure prints a readable
# message and LEAVES THE WINDOW OPEN. (The old script called `exit`,
# which closes the PowerShell window when run via `iex (irm ...)` -- so
# any error vanished before you could read it.)
try {
    Write-YumiiBanner

    # -- 0: onboarding (skipped on updates -- existing settings win) ----------
    $freshSetup = Start-Onboarding

    # -- 1/4: uv --------------------------------------------------------------
    Write-Host ""
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
    if (-not $freshSetup) {
        Write-Host "  (Your settings were kept -- model downloads happen on first launch.)" -ForegroundColor DarkGray
    }
    Write-Host "  To update later: re-run this same command." -ForegroundColor DarkGray
    Write-Host "  To uninstall: uv tool uninstall yumii, then remove %LOCALAPPDATA%\Yumii." -ForegroundColor DarkGray
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
