#Requires -Version 5.1
<#
.SYNOPSIS
  바탕화면(선택: 시작 메뉴)에 로컬 Streamlit 바로가기를 등록한다.

.DESCRIPTION
  대상: scripts\launch-local-app.ps1
  바로가기 이름: AI 업무자동화.lnk

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\register-local-app-shortcut.ps1
  powershell -ExecutionPolicy Bypass -File scripts\register-local-app-shortcut.ps1 -StartMenu
#>
param(
    [switch]$StartMenu
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Launch = (Resolve-Path (Join-Path $PSScriptRoot "launch-local-app.ps1")).Path
$ShortcutName = "AI 업무자동화.lnk"

function New-LocalAppShortcut([string]$LnkPath) {
    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($LnkPath)
    $lnk.TargetPath = "powershell.exe"
    $lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Launch`""
    $lnk.WorkingDirectory = $RepoRoot
    $lnk.WindowStyle = 7  # minimized
    $lnk.Description = "AI 업무자동화 (local Streamlit)"
    $lnk.Save()
    Write-Host "Created: $LnkPath"
}

$Desktop = [Environment]::GetFolderPath("Desktop")
$desktopLnk = Join-Path $Desktop $ShortcutName
New-LocalAppShortcut $desktopLnk

if ($StartMenu) {
    $programs = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"
    if (-not (Test-Path -LiteralPath $programs)) {
        New-Item -ItemType Directory -Force -Path $programs | Out-Null
    }
    $startLnk = Join-Path $programs $ShortcutName
    New-LocalAppShortcut $startLnk
}