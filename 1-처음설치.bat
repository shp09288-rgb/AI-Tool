@echo off
setlocal
cd /d "%~dp0"
echo.
echo ============================================================
echo   AI Work Automation - First install
echo ============================================================
echo   Please wait. Do not close this window.
echo ============================================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\first-install.ps1"
set ERR=%ERRORLEVEL%
echo.
if not "%ERR%"=="0" (
  echo [FAILED] Exit code %ERR%
  echo Open and read: 00-HERE guide markdown in this folder
  echo File name starts with 00-
  pause
  exit /b %ERR%
)
echo [OK] Follow Salesforce login steps shown above.
pause
exit /b 0