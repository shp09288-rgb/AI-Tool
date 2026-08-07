#Requires -Version 5.1
<#
.SYNOPSIS
  Hub PC용 Streamlit 자동 기동 (재부팅/로그인 후).

.DESCRIPTION
  - Tailscale·OneDrive가 뜰 시간을 위해 기본 90초 대기
  - 기존 webui Streamlit 프로세스가 있으면 종료 후 재기동
  - 0.0.0.0:8501 바인딩 → Tailscale 피어에서 접속 가능
  - 로그: <repo>\logs\hub-streamlit.log
#>
param(
    [int]$DelaySeconds = 90,
    [int]$Port = 8501,
    [string]$Address = "0.0.0.0"
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvStreamlit = Join-Path $RepoRoot ".venv\Scripts\streamlit.exe"
$WebUi = Join-Path $RepoRoot "src\ai_work_automation\webui.py"
$LogDir = Join-Path $RepoRoot "logs"
$LogFile = Join-Path $LogDir "hub-streamlit.log"

function Write-Log([string]$Message) {
    $line = "{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $Message
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $line
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Set-Location $RepoRoot

Write-Log "start-hub-streamlit: repo=$RepoRoot delay=${DelaySeconds}s port=$Port"

if (-not (Test-Path $VenvStreamlit)) {
    Write-Log "ERROR: missing $VenvStreamlit — run: python -m venv .venv && pip install -e `".[ui]`""
    exit 1
}
if (-not (Test-Path $WebUi)) {
    Write-Log "ERROR: missing $WebUi"
    exit 1
}

if ($DelaySeconds -gt 0) {
    Write-Log "waiting ${DelaySeconds}s for Tailscale/OneDrive..."
    Start-Sleep -Seconds $DelaySeconds
}

# 이전 hub Streamlit 정리 (같은 포트)
try {
    $listeners = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $listeners) {
        if ($procId -and $procId -gt 0) {
            Write-Log "stopping PID $procId on port $Port"
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
} catch {
    Write-Log "port cleanup skipped: $($_.Exception.Message)"
}

$env:PYTHONPATH = Join-Path $RepoRoot "src"
$args = @(
    "run", $WebUi,
    "--server.address", $Address,
    "--server.port", "$Port",
    "--server.headless", "true",
    "--browser.gatherUsageStats", "false"
)

Write-Log "launching: $VenvStreamlit $($args -join ' ')"
$proc = Start-Process -FilePath $VenvStreamlit -ArgumentList $args `
    -WorkingDirectory $RepoRoot `
    -WindowStyle Hidden `
    -RedirectStandardOutput (Join-Path $LogDir "hub-streamlit.out.log") `
    -RedirectStandardError (Join-Path $LogDir "hub-streamlit.err.log") `
    -PassThru

Write-Log "started PID=$($proc.Id) — Tailscale에서 http://<이-PC-MagicDNS>:$Port 접속"
exit 0
