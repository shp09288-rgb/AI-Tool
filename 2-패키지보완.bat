@echo off
setlocal
cd /d "%~dp0"
echo Repairing environment (broken .venv / missing packages)...
echo This may take a few minutes.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\first-install.ps1"
set ERR=%ERRORLEVEL%
echo.
if not "%ERR%"=="0" (
  echo [FAILED] Exit code %ERR%
  echo Tip: delete the .venv folder manually, then run 1-first-install bat again.
  pause
  exit /b %ERR%
)
echo [OK] Now double-click the desktop shortcut.
pause
exit /b 0