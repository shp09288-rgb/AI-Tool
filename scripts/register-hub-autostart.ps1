#Requires -Version 5.1
<#
.SYNOPSIS
  로그인 시 Streamlit hub를 자동 기동하는 작업 스케줄러 등록.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\register-hub-autostart.ps1
  powershell -ExecutionPolicy Bypass -File scripts\register-hub-autostart.ps1 -DelaySeconds 120
#>
param(
    [int]$DelaySeconds = 90,
    [int]$Port = 8501,
    [string]$TaskName = "AI-Work-Automation-Hub-Streamlit",
    [switch]$Unregister
)

$ErrorActionPreference = "Stop"
$StartScript = (Resolve-Path (Join-Path $PSScriptRoot "start-hub-streamlit.ps1")).Path

if ($Unregister) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed task: $TaskName"
    exit 0
}

$arg = "-NoProfile -ExecutionPolicy Bypass -File `"$StartScript`" -DelaySeconds $DelaySeconds -Port $Port"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arg
# 사용자 로그온 시 (Outlook/Excel COM도 같은 대화형 세션 필요)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 2)
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Force | Out-Null

Write-Host "Registered: $TaskName"
Write-Host "  At logon → $StartScript (delay ${DelaySeconds}s, port $Port)"
Write-Host "  Test now: powershell -ExecutionPolicy Bypass -File `"$StartScript`" -DelaySeconds 0"
Write-Host "  Remove:   powershell -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Unregister"
