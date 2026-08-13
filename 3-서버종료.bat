@echo off
setlocal
cd /d "%~dp0"
echo Stopping local Streamlit (port 8501) so folders/logs unlock...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-local-app.ps1"
set ERR=%ERRORLEVEL%
echo.
if not "%ERR%"=="0" (
  echo [WARN] Something may still be running. Close browser tabs to localhost:8501 and retry.
  pause
  exit /b %ERR%
)
echo [OK] Now you can delete old Downloads\AI-Tool-* folders.
echo Then unzip a fresh ZIP and run 1-first-install bat.
pause
exit /b 0