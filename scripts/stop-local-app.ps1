#Requires -Version 5.1
<#
.SYNOPSIS
  Stop local Streamlit on port 8501 so logs unlock and folder can be deleted.
#>
param(
    [int]$Port = 8501
)

$ErrorActionPreference = "Continue"

Write-Host "Stopping listeners on port $Port ..."

$pids = @()
try {
    $pids = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
} catch {}

foreach ($procId in $pids) {
    if ($procId -and $procId -gt 0) {
        Write-Host "  Stopping PID $procId (port $Port)"
        Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
    }
}

# Also stop streamlit/webui python processes (covers Downloads ZIP paths)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -and (
            $_.CommandLine -match 'streamlit' -or
            $_.CommandLine -match 'webui\.py' -or
            $_.CommandLine -match 'AI-Tool'
        )
    } |
    ForEach-Object {
        Write-Host "  Stopping PID $($_.ProcessId) (streamlit/webui)"
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

Start-Sleep -Seconds 1
$still = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($still) {
    Write-Host "[WARN] Port $Port still in use. Close other terminals and retry."
    exit 1
}

Write-Host "[OK] Port $Port is free. You can delete old AI-Tool folders now."
exit 0
