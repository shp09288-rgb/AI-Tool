@echo off
setlocal
cd /d "%~dp0"
echo.
echo === Register desktop shortcut ===
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\register-local-app-shortcut.ps1" %*
set ERR=%ERRORLEVEL%
echo.
if not "%ERR%"=="0" (
  echo [FAILED] Shortcut registration failed. Exit code %ERR%
  pause
  exit /b %ERR%
)
echo [OK] Desktop shortcut created: AI Work Automation
echo Optional Start Menu:  this-bat -StartMenu
pause
exit /b 0