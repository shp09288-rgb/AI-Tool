#Requires -Version 5.1
<#
.SYNOPSIS
  Clean PC / ZIP first install: venv, pip ui extras, config copy, desktop shortcut.
#>
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $RepoRoot

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host $Message
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  AI Work Automation - First install (ZIP / clean PC)"
Write-Host "============================================================"
Write-Host "  Do not close this window until it finishes."
Write-Host "============================================================"

if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "pyproject.toml"))) {
    Write-Host "[ERROR] Wrong folder. Run from the unzipped repo root"
    Write-Host "        (same folder as 00-여기부터-읽으세요.md and pyproject.toml)."
    exit 1
}

Write-Step "[1/5] Checking Python..."
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "[NEED] Python not found on PATH."
    Write-Host "  1) https://www.python.org/downloads/"
    Write-Host "  2) Check 'Add python.exe to PATH' during install"
    Write-Host "  3) Restart PC, then run 1-처음설치.bat again"
    Start-Process "https://www.python.org/downloads/"
    exit 1
}
& python --version

Write-Step "[2/5] Preparing .venv ..."
$venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPy)) {
    & python -m venv (Join-Path $RepoRoot ".venv")
    if ($LASTEXITCODE -ne 0) { throw "venv create failed" }
} else {
    Write-Host "      Reusing existing .venv"
}

Write-Step "[3/5] Installing packages (may take a few minutes)..."
& $venvPy -m pip install -U pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $venvPy -m pip install -e ".[ui]"
if ($LASTEXITCODE -ne 0) { throw "pip install -e .[ui] failed" }

Write-Step "[4/5] Copying config files..."
$envPath = Join-Path $RepoRoot ".env"
$envExample = Join-Path $RepoRoot ".env.example"
if (-not (Test-Path -LiteralPath $envPath) -and (Test-Path -LiteralPath $envExample)) {
    Copy-Item -LiteralPath $envExample -Destination $envPath
    Write-Host "      created .env"
} else {
    Write-Host "      .env ok"
}
$settings = Join-Path $RepoRoot "config\settings.yaml"
$settingsExample = Join-Path $RepoRoot "config\settings.example.yaml"
if (-not (Test-Path -LiteralPath $settings) -and (Test-Path -LiteralPath $settingsExample)) {
    Copy-Item -LiteralPath $settingsExample -Destination $settings
    Write-Host "      created config\settings.yaml"
} else {
    Write-Host "      settings.yaml ok"
}

Write-Step "[5/5] Creating desktop shortcut..."
$reg = Join-Path $PSScriptRoot "register-local-app-shortcut.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $reg
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Shortcut registration failed. Later run 등록-로컬앱.bat"
} else {
    Write-Host "      Desktop shortcut 'AI 업무자동화' created."
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  Auto-install steps finished."
Write-Host "============================================================"
Write-Host ""
Write-Host "  NEXT (you must do this once): Salesforce login"
Write-Host "  1. Open PowerShell"
Write-Host "  2. Paste and Enter:"
Write-Host "       sf org login web --alias parksystems"
Write-Host "  3. Log in with company Salesforce in the browser"
Write-Host "  4. Double-click desktop shortcut: AI 업무자동화"
Write-Host ""
Write-Host "  Guide: 00-여기부터-읽으세요.md"
Write-Host "  If sf is missing: https://developer.salesforce.com/tools/salesforcecli"
Write-Host ""
exit 0