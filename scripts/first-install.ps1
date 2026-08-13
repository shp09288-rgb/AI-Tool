#Requires -Version 5.1
<#
.SYNOPSIS
  Clean PC / ZIP first install: venv, pip ui extras, Salesforce CLI, config, shortcut.
#>
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location -LiteralPath $RepoRoot

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host $Message
}

function Refresh-PathFromRegistry {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ";"
}

function Ensure-SfBinOnUserPath {
    <#
      Official installer puts files under Program Files\sf\bin and may register
      User PATH — but the current process still has a stale Path. Also ensure
      the User PATH entry exists if sf.cmd is on disk.
    #>
    $candidates = @(
        (Join-Path $env:ProgramFiles "sf\bin"),
        (Join-Path $env:LOCALAPPDATA "sf\bin"),
        (Join-Path $env:APPDATA "npm")
    )
    $bin = $null
    foreach ($dir in $candidates) {
        if ((Test-Path -LiteralPath (Join-Path $dir "sf.cmd")) -or (Test-Path -LiteralPath (Join-Path $dir "sf.exe"))) {
            $bin = $dir
            break
        }
    }
    if (-not $bin) { return $false }

    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @()
    if ($userPath) { $parts = $userPath -split ";" | Where-Object { $_ } }
    $normalized = $parts | ForEach-Object { $_.TrimEnd("\") }
    if ($normalized -notcontains $bin.TrimEnd("\")) {
        Write-Host "      Adding to User PATH: $bin"
        $newUser = (@($parts + $bin) | Where-Object { $_ }) -join ";"
        [Environment]::SetEnvironmentVariable("Path", $newUser, "User")
    }
    Refresh-PathFromRegistry
    if ($env:Path -notlike "*$bin*") {
        $env:Path = "$bin;$env:Path"
    }
    return $true
}

function Test-SfCliAvailable {
    Refresh-PathFromRegistry
    Ensure-SfBinOnUserPath | Out-Null
    $cmd = Get-Command sf -ErrorAction SilentlyContinue
    if (-not $cmd) {
        # Direct path fallback (stale Get-Command cache / PATH)
        $direct = @(
            (Join-Path $env:ProgramFiles "sf\bin\sf.cmd"),
            (Join-Path $env:LOCALAPPDATA "sf\bin\sf.cmd"),
            (Join-Path $env:APPDATA "npm\sf.cmd")
        ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if (-not $direct) { return $false }
        & $direct version 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    }
    & sf version 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Install-SalesforceCli {
    if (Test-SfCliAvailable) {
        Write-Host "      Salesforce CLI (sf) already available"
        & sf version 2>$null | Select-Object -First 1
        return $true
    }

    Write-Host "      sf not found — installing Salesforce CLI (may need a minute)..."

    # 1) Official Windows x64 installer (silent)
    $installer = Join-Path $env:TEMP "sf-x64-ai-tool.exe"
    $url = "https://developer.salesforce.com/media/salesforce-cli/sf/channels/stable/sf-x64.exe"
    try {
        Write-Host "      Downloading sf-x64.exe ..."
        Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing
        Write-Host "      Running silent installer (/S) ..."
        $p = Start-Process -FilePath $installer -ArgumentList "/S" -Wait -PassThru
        Write-Host "      installer exit=$($p.ExitCode)"
    } catch {
        Write-Host "      [WARN] Download/install failed: $($_.Exception.Message)"
    }

    if (Test-SfCliAvailable) {
        Write-Host "      Salesforce CLI installed OK"
        Ensure-SfBinOnUserPath | Out-Null
        & sf version 2>$null | Select-Object -First 1
        return $true
    }

    # Installer may have written files but PATH not visible yet — force PATH repair once
    if (Ensure-SfBinOnUserPath) {
        Write-Host "      Found sf on disk; repaired PATH and re-checking..."
        if (Test-SfCliAvailable) {
            Write-Host "      Salesforce CLI available after PATH repair"
            & sf version 2>$null | Select-Object -First 1
            return $true
        }
    }

    # 2) Fallback: winget (older sfdx package — last resort)
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "      Trying winget Salesforce.sfdx-cli ..."
        try {
            & winget install --id Salesforce.sfdx-cli -e --silent --accept-package-agreements --accept-source-agreements
        } catch {
            Write-Host "      [WARN] winget install failed"
        }
        if (Test-SfCliAvailable) {
            Write-Host "      Salesforce CLI available after winget"
            return $true
        }
    }

    # 3) Fallback: npm global
    $npm = Get-Command npm -ErrorAction SilentlyContinue
    if ($npm) {
        Write-Host "      Trying npm install -g @salesforce/cli ..."
        try {
            & npm install -g "@salesforce/cli"
        } catch {
            Write-Host "      [WARN] npm install failed"
        }
        if (Test-SfCliAvailable) {
            Write-Host "      Salesforce CLI available after npm"
            return $true
        }
    }

    Write-Host "      [WARN] Could not install sf automatically."
    Write-Host "             Install manually: https://developer.salesforce.com/tools/salesforcecli"
    Write-Host "             Then open a NEW PowerShell and run: sf org login web --alias parksystems"
    Start-Process "https://developer.salesforce.com/tools/salesforcecli"
    return $false
}

function Test-VenvHealthy([string]$Root) {
    $cfg = Join-Path $Root ".venv\pyvenv.cfg"
    $py = Join-Path $Root ".venv\Scripts\python.exe"
    if (-not (Test-Path -LiteralPath $cfg)) { return $false }
    if (-not (Test-Path -LiteralPath $py)) { return $false }
    & $py -c "import sys; print(sys.prefix)" 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

function Reset-Venv([string]$Root) {
    $venvDir = Join-Path $Root ".venv"
    if (Test-Path -LiteralPath $venvDir) {
        Write-Host "      Removing broken .venv ..."
        Remove-Item -LiteralPath $venvDir -Recurse -Force -ErrorAction Stop
    }
    Write-Host "      Creating new .venv ..."
    & python -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw "venv create failed" }
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  AI Work Automation - First install (ZIP / clean PC)"
Write-Host "============================================================"
Write-Host "  Do not close this window until it finishes."
Write-Host "============================================================"

if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "pyproject.toml"))) {
    Write-Host "[ERROR] Wrong folder. Run from the unzipped repo root"
    Write-Host "        (same folder as 00-HERE guide and pyproject.toml)."
    exit 1
}

Write-Step "[1/6] Checking Python..."
$pyCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    Write-Host "[NEED] Python not found on PATH."
    Write-Host "  1) https://www.python.org/downloads/"
    Write-Host "  2) Check 'Add python.exe to PATH' during install"
    Write-Host "  3) Restart PC, then run 1-first-install bat again"
    Start-Process "https://www.python.org/downloads/"
    exit 1
}
& python --version

Write-Step "[2/6] Preparing .venv ..."
$venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (Test-VenvHealthy $RepoRoot) {
    Write-Host "      Reusing healthy .venv"
} else {
    if (Test-Path -LiteralPath (Join-Path $RepoRoot ".venv")) {
        Write-Host "      .venv is broken (missing pyvenv.cfg or python) — recreating"
    }
    Reset-Venv $RepoRoot
}
$venvPy = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-VenvHealthy $RepoRoot)) {
    throw "venv still unhealthy after recreate"
}

Write-Step "[3/6] Installing Python packages (may take a few minutes)..."
& $venvPy -m pip install -U pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
& $venvPy -m pip install -e ".[ui]"
if ($LASTEXITCODE -ne 0) { throw "pip install -e .[ui] failed" }
& $venvPy -m pip install "openpyxl>=3.1"
if ($LASTEXITCODE -ne 0) { throw "pip install openpyxl failed" }
& $venvPy -c "import openpyxl, streamlit"
if ($LASTEXITCODE -ne 0) { throw "import check failed after install" }
Write-Host "      import check OK (openpyxl, streamlit)"

Write-Step "[4/6] Installing Salesforce CLI (sf) if missing..."
$sfOk = Install-SalesforceCli
if ($sfOk) {
    Write-Host "      sf is ready (login still required once in browser)"
} else {
    Write-Host "      [WARN] continuing without sf — app UI will work; Salesforce features need sf later"
}

Write-Step "[5/6] Copying config files..."
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

Write-Step "[6/6] Creating desktop shortcut..."
$reg = Join-Path $PSScriptRoot "register-local-app-shortcut.ps1"
& powershell -NoProfile -ExecutionPolicy Bypass -File $reg
if ($LASTEXITCODE -ne 0) {
    Write-Host "[WARN] Shortcut registration failed. Later run register-local-app bat"
} else {
    Write-Host "      Desktop shortcut created."
}

Write-Host ""
Write-Host "============================================================"
Write-Host "  Auto-install steps finished."
Write-Host "============================================================"
Write-Host ""
Write-Host "  NEXT (you must do this once): Salesforce login"
Write-Host "  1. Open a NEW PowerShell window"
Write-Host "  2. Paste and Enter:"
Write-Host "       sf org login web --alias parksystems"
Write-Host "  3. Log in with company Salesforce in the browser"
Write-Host "  4. Double-click desktop shortcut"
Write-Host "  5. Settings tab -> SF status refresh"
Write-Host ""
Write-Host "  Guide: 00-HERE markdown in this folder"
Write-Host ""
exit 0
