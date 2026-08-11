<#
.SYNOPSIS
Cold start for WhispBot on Windows: checks/Installs prerequisites, then launches the bot in the foreground.
.DESCRIPTION
Performs the following steps:
  1. Ensures PowerShell execution policy allows running scripts (RemoteSigned for current user).
  2. Copies .env.example to .env if .env is missing.
  3. Verifies Python (≥3.10) is available.
  4. Installs uv via pip if not present.
  5. Runs `uv sync` to create/update the virtual environment and install dependencies.
  6. Checks that ffmpeg is installed and accessible.
  7. Finally launches the bot in the foreground using scripts\start-cli.ps1 so you can see the output.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

# Helper to write colored messages
function Write-Info($msg) { Write-Host "[Bot] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[Bot] WARNING: $msg" -ForegroundColor Yellow }
function Write-Error($msg) { Write-Host "[Bot] ERROR: $msg" -ForegroundColor Red }

# 1. Execution policy
Write-Info "Checking PowerShell execution policy..."
$policy = Get-ExecutionPolicy -Scope CurrentUser
if ($policy -eq "RemoteSigned") {
    Write-Info "Execution policy is already RemoteSigned for current user."
}
else {
    try {
        Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned -Force
        Write-Info "Execution policy set to RemoteSigned for current user."
    }
    catch {
        Write-Error "Failed to set execution policy. You may need to run PowerShell as Administrator or set it manually:"
        Write-Error "  Set-ExecutionPolicy -Scope CurrentUser RemoteSigned"
        exit 1
    }
}

# 2. .env file
Write-Info "Checking for .env file..."
$projectRoot = Split-Path -Parent $PSScriptRoot
$envPath = Join-Path $projectRoot ".env"
$envExamplePath = Join-Path $projectRoot ".env.example"
if (-not (Test-Path $envPath)) {
    if (Test-Path $envExamplePath) {
        Copy-Item -Path $envExamplePath -Destination $envPath
        Write-Info ".env created from .env.example. Please edit it with your settings before proceeding."
    }
    else {
        Write-Error ".env.example not found. Cannot create .env."
        exit 1
    }
}
else {
    Write-Info ".env file found."
}

# 3. Python version
Write-Info "Checking Python availability..."
# Try py -3 first (Windows launcher), then python
$pythonExe = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $versionOutput = py -3 --version 2>&1
    if ($versionOutput -match 'Python (\d+\.\d+)') {
        $version = [Version]$matches[1]
        if ($version -ge [Version]"3.10") {
            $pythonExe = "py -3"
            Write-Info "Found Python $version via py -3"
        }
    }
}
if (-not $pythonExe) {
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $versionOutput = python --version 2>&1
        if ($versionOutput -match 'Python (\d+\.\d+)') {
            $version = [Version]$matches[1]
            if ($version -ge [Version]"3.10") {
                $pythonExe = "python"
                Write-Info "Found Python $version via python"
            }
        }
    }
}
if (-not $pythonExe) {
    Write-Error "Python 3.10 or newer not found. Please install Python from https://www.python.org/downloads/"
    exit 1
}

# 4. uv installation
Write-Info "Checking for uv..."
if (Get-Command uv -ErrorAction SilentlyContinue) {
    Write-Info "uv is already installed."
}
else {
    Write-Info "uv not found. Installing uv via pip..."
    try {
        & $pythonExe -m pip install --upgrade pip
        & $pythonExe -m pip install uv
        Write-Info "uv installed successfully."
    }
    catch {
        Write-Error "Failed to install uv. Please install it manually (e.g., pip install uv)."
        exit 1
    }
}

# 5. uv sync (install dependencies)
Write-Info "Synchronizing dependencies with uv sync..."
& uv sync
if ($LASTEXITCODE -ne 0) {
    Write-Error "uv sync failed. Check output above."
    exit 1
}
Write-Info "Dependencies synchronized."

# 6. ffmpeg check
Write-Info "Checking for ffmpeg..."
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    Write-Error "ffmpeg not found. Please install ffmpeg and ensure it is in your PATH."
    Write-Error "On Windows you can use chocolatey: choco install ffmpeg"
    Write-Error "Or download from https://ffmpeg.org/download.html"
    exit 1
}
else {
    Write-Info "ffmpeg found."
}

# 7. Launch bot in foreground
Write-Info "All checks passed. Launching bot in foreground..."
& "$PSScriptRoot\start-cli.ps1"
# Propagate exit code
exit $LASTEXITCODE