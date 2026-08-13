#Requires -Version 5.1
<#
.SYNOPSIS
  로컬 PC용 Streamlit 기동 + 브라우저 오픈.

.DESCRIPTION
  - 기본 바인딩: 127.0.0.1:8501 (0.0.0.0 사용 안 함)
  - 이미 Listen 중이면 프로세스 종료/재기동하지 않고 브라우저만 오픈
  - 경로에 공백/한글이 있어도 동작하도록 8.3 short path + python -m streamlit 사용
  - 로그: <repo>\logs\local-app.log
#>
param(
    [int]$DelaySeconds = 0,
    [int]$Port = 8501,
    [string]$Address = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Refresh-PathFromRegistry {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = (@($machine, $user) | Where-Object { $_ }) -join ";"
    foreach ($dir in @(
        (Join-Path $env:ProgramFiles "sf\bin"),
        (Join-Path $env:LOCALAPPDATA "sf\bin"),
        (Join-Path $env:APPDATA "npm")
    )) {
        if ((Test-Path -LiteralPath (Join-Path $dir "sf.cmd")) -or (Test-Path -LiteralPath (Join-Path $dir "sf.exe"))) {
            if ($env:Path -notlike "*$dir*") {
                $env:Path = "$dir;$env:Path"
            }
        }
    }
}

function Get-ShortPath([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return $Path }
    $fso = New-Object -ComObject Scripting.FileSystemObject
    if (Test-Path -LiteralPath $Path -PathType Container) {
        return $fso.GetFolder($Path).ShortPath
    }
    return $fso.GetFile($Path).ShortPath
}

$RepoShort = Get-ShortPath $RepoRoot
$VenvPython = Join-Path $RepoShort ".venv\Scripts\python.exe"
$WebUi = Join-Path $RepoShort "src\ai_work_automation\webui.py"
$LogDir = Join-Path $RepoRoot "logs"
$LogFile = Join-Path $LogDir "local-app.log"
$BrowserUrl = "http://127.0.0.1:$Port"

function Write-Log([string]$Message) {
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $line
}

function Test-PortListening {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Test-AppHealthy {
    try {
        $h = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/_stcore/health" -UseBasicParsing -TimeoutSec 3
        return ($h.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Stop-LocalListeners {
    $stopScript = Join-Path $PSScriptRoot "stop-local-app.ps1"
    if (Test-Path -LiteralPath $stopScript) {
        & powershell -NoProfile -ExecutionPolicy Bypass -File $stopScript -Port $Port | Out-Null
    } else {
        $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($procId in $listeners) {
            if ($procId -and $procId -gt 0) {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Start-Sleep -Seconds 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $RepoShort
Refresh-PathFromRegistry
Write-Log "launch-local-app: repo=$RepoRoot short=$RepoShort delay=${DelaySeconds}s address=$Address port=$Port"

if ($Address -eq "0.0.0.0") {
    Write-Log "ERROR: address 0.0.0.0 is not allowed for local launcher; use 127.0.0.1"
    exit 1
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Log "ERROR: missing $VenvPython — run 1-처음설치.bat (or: python -m venv .venv && pip install -e `".[ui]`")"
    exit 1
}
if (-not (Test-Path -LiteralPath $WebUi)) {
    Write-Log "ERROR: missing $WebUi"
    exit 1
}

# Self-heal missing deps from older ZIP installs (e.g. openpyxl)
$needInstall = $false
& $VenvPython -c "import openpyxl" 2>$null
if ($LASTEXITCODE -ne 0) { $needInstall = $true }
& $VenvPython -c "import streamlit" 2>$null
if ($LASTEXITCODE -ne 0) { $needInstall = $true }
if ($needInstall) {
    Write-Log "missing packages detected — running: pip install -e `".[ui]`""
    Set-Location $RepoShort
    & $VenvPython -m pip install -e ".[ui]"
    if ($LASTEXITCODE -ne 0) {
        Write-Log "ERROR: pip install -e .[ui] failed"
        exit 1
    }
    & $VenvPython -c "import openpyxl" 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Log "ERROR: openpyxl still missing after install"
        exit 1
    }
    Write-Log "dependencies OK"
}

if ($DelaySeconds -gt 0) {
    Write-Log "waiting ${DelaySeconds}s..."
    Start-Sleep -Seconds $DelaySeconds
}

if (Test-PortListening) {
    if (Test-AppHealthy) {
        Write-Log "healthy server already on port $Port — opening browser only"
        Start-Process $BrowserUrl
        exit 0
    }
    Write-Log "port $Port is in use but unhealthy (or Internal Server Error) — restarting"
    Stop-LocalListeners
}

$env:PYTHONPATH = Join-Path $RepoShort "src"
$argList = @(
    "-m", "streamlit", "run", $WebUi,
    "--server.address=$Address",
    "--server.port=$Port",
    "--server.headless=true",
    "--browser.gatherUsageStats=false"
)

Write-Log "launching: $VenvPython $($argList -join ' ')"
$outLog = Join-Path $LogDir "local-app.out.log"
$errLog = Join-Path $LogDir "local-app.err.log"
$proc = Start-Process -FilePath $VenvPython -ArgumentList $argList `
    -WorkingDirectory $RepoShort `
    -WindowStyle Hidden `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog `
    -PassThru

$deadline = (Get-Date).AddSeconds(15)
$listening = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 1
    if ($proc.HasExited) {
        Write-Log "ERROR: Streamlit exited early code=$($proc.ExitCode). See $errLog"
        if (Test-Path $errLog) {
            Get-Content $errLog -Tail 20 | ForEach-Object { Write-Log "err: $_" }
        }
        exit 1
    }
    if (Test-PortListening) {
        $listening = $true
        break
    }
}

if (-not $listening) {
    Write-Log "WARNING: process alive but port $Port not listening yet — opening browser anyway; check $errLog"
} else {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    Write-Log "listening on $($conn.LocalAddress):$Port PID=$($conn.OwningProcess)"
}

Write-Log "started PID=$($proc.Id) — opening $BrowserUrl"
Start-Process $BrowserUrl
exit 0
