# ==========================================
#           ARXH INSTALLER (Windows)
# ==========================================
# Run:  powershell -ExecutionPolicy Bypass -File .\install.ps1

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectDir
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

function Info($m) { Write-Host "[i] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "[FATAL] $m" -ForegroundColor Red; exit 1 }
function Refresh-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}

Write-Host ""
Write-Host "  archie installer (Windows) - v0.4" -ForegroundColor Green
Write-Host ""

# ---------- Python ----------
function Find-Python {
    foreach ($c in @(@("py", "-3"), @("python"), @("python3"))) {
        if (-not (Get-Command $c[0] -ErrorAction SilentlyContinue)) { continue }
        $extra = @()
        if ($c.Count -gt 1) { $extra = $c[1..($c.Count - 1)] }
        try {
            $v = & $c[0] @extra -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
            if ($LASTEXITCODE -eq 0 -and [version]$v -ge [version]"3.9") {
                return @{ Exe = $c[0]; Args = $extra }
            }
        } catch {}
    }
    return $null
}

$py = Find-Python
if (-not $py) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Info "Python 3.9+ not found - installing via winget..."
        winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
        Refresh-Path
        $py = Find-Python
    }
    if (-not $py) { Fail "Install Python 3.9+ from https://python.org (tick 'Add to PATH'), open a NEW terminal, re-run." }
}
Ok "Python found"

# ---------- Config ----------
$ConfFile = Join-Path $ProjectDir "arxh.conf"
if (-not (Test-Path $ConfFile)) {
    Info "No arxh.conf yet - starting the setup wizard..."
    & $py.Exe @($py.Args) (Join-Path $ProjectDir "archie_setup.py")
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $ConfFile)) { Fail "Setup wizard didn't finish." }
}

function Read-Conf($path) {
    $h = @{}
    foreach ($l in Get-Content $path -Encoding UTF8) {
        if ($l -match '^\s*([A-Z_]+)="(.*)"\s*$') { $h[$Matches[1]] = $Matches[2] }
    }
    return $h
}
function Set-ConfValue($key, $value) {
    $text = [IO.File]::ReadAllText($ConfFile)
    $text = [regex]::Replace($text, "(?m)^$key=.*$", { param($m) "$key=`"$value`"" })
    [IO.File]::WriteAllText($ConfFile, $text, (New-Object Text.UTF8Encoding $false))
}
$conf = Read-Conf $ConfFile
$profileType = if ($conf["PROFILE_TYPE"]) { $conf["PROFILE_TYPE"] } else { "cli" }
Ok "Loaded config: $($conf['BOT_NAME']) | Profile=$profileType | Local=$($conf['LOCAL']) | API=$($conf['API'])"

# ---------- venv + packages ----------
Info "[1/3] Creating virtual environment..."
if (-not (Test-Path (Join-Path $ProjectDir "venv"))) {
    & $py.Exe @($py.Args) -m venv (Join-Path $ProjectDir "venv")
    if ($LASTEXITCODE -ne 0) { Fail "Couldn't create venv." }
}
$vpy = Join-Path $ProjectDir "venv\Scripts\python.exe"

Info "[2/3] Installing Python packages..."
& $vpy -m pip install --upgrade pip setuptools wheel
& $vpy -m pip install -r (Join-Path $ProjectDir "requirements.txt")
if ($LASTEXITCODE -ne 0) { Fail "pip install failed." }
if ($profileType -eq "discord") { & $vpy -m pip install discord.py }
if ($profileType -eq "gui") {
    & $vpy -c "import tkinter" 2>$null
    if ($LASTEXITCODE -ne 0) { Warn "Tkinter missing - reinstall Python from python.org with 'tcl/tk' ticked." }
}

# ---------- Ollama ----------
$needOllama = ($conf["LOCAL"] -eq "True") -or ($conf["VISION_ENABLED"] -eq "True")
if ($needOllama) {
    Info "[3/3] Setting up Ollama..."
    $ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
    if (-not $ollama) {
        $cand = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"
        if (Test-Path $cand) { $ollama = $cand }
    }
    if (-not $ollama) {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { Fail "Install Ollama from https://ollama.com/download, then re-run." }
        winget install -e --id Ollama.Ollama --accept-source-agreements --accept-package-agreements
        Refresh-Path
        $ollama = (Get-Command ollama -ErrorAction SilentlyContinue).Source
        if (-not $ollama) { $ollama = Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe" }
    }

    # Keep models inside the project (like the Linux installer does)
    $ModelsDir = Join-Path $ProjectDir "MODELS"
    New-Item -ItemType Directory -Force -Path $ModelsDir | Out-Null
    if ([Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "User") -ne $ModelsDir) {
        [Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $ModelsDir, "User")
        Get-Process -Name "ollama*" -ErrorAction SilentlyContinue | Stop-Process -Force
        Start-Sleep -Seconds 1
    }
    $env:OLLAMA_MODELS = $ModelsDir

    $up = $false
    try { Invoke-WebRequest "http://127.0.0.1:11434" -UseBasicParsing -TimeoutSec 2 | Out-Null; $up = $true } catch {}
    if (-not $up) {
        Start-Process -FilePath $ollama -ArgumentList "serve" -WindowStyle Hidden
        for ($i = 0; $i -lt 20 -and -not $up; $i++) {
            Start-Sleep -Milliseconds 500
            try { Invoke-WebRequest "http://127.0.0.1:11434" -UseBasicParsing -TimeoutSec 2 | Out-Null; $up = $true } catch {}
        }
    }
    if (-not $up) { Warn "Ollama server didn't answer; pulls may fail." }

    function Pull-Model($name) {
        while ($true) {
            Info "Pulling model: $name"
            & $ollama pull $name
            if ($LASTEXITCODE -eq 0) { return $name }
            $new = Read-Host "That model doesn't exist. Write another (or 'skip')"
            if ($new -eq "skip") { Warn "Skipped - run 'ollama pull <model>' later."; return $name }
            if ($new) { $name = $new }
        }
    }
    if ($conf["LOCAL"] -eq "True") {
        $m = Pull-Model $conf["OLLAMA_MODEL"]
        if ($m -ne $conf["OLLAMA_MODEL"]) { Set-ConfValue "OLLAMA_MODEL" $m }
    }
    if ($conf["VISION_ENABLED"] -eq "True") {
        $m = Pull-Model $conf["VISION_MODEL"]
        if ($m -ne $conf["VISION_MODEL"]) { Set-ConfValue "VISION_MODEL" $m }
    }
}

# ---------- archie-agent command ----------
$BinDir = Join-Path $env:LOCALAPPDATA "Archie\bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$cmd = "@echo off`r`n" +
       "set `"ARCHIE_HOME=$ProjectDir`"`r`n" +
       "if not defined OLLAMA_MODELS set `"OLLAMA_MODELS=$ProjectDir\MODELS`"`r`n" +
       "`"$vpy`" `"$ProjectDir\archie_agent.py`" %*`r`n"
Set-Content -Path (Join-Path $BinDir "archie-agent.cmd") -Value $cmd -Encoding OEM

$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not $userPath) { $userPath = "" }
if (-not (($userPath -split ";") | Where-Object { $_ -ieq $BinDir })) {
    [Environment]::SetEnvironmentVariable("Path", ($userPath.TrimEnd(";") + ";" + $BinDir), "User")
    $env:Path += ";$BinDir"
}
Ok "Installed command: archie-agent  ($BinDir)"

Write-Host ""
Write-Host "  [OK] installation success!" -ForegroundColor Green
Write-Host "  Open a NEW terminal and run:  archie-agent --cli" -ForegroundColor Green
Write-Host ""
