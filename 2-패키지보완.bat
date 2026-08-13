@echo off
setlocal
cd /d "%~dp0"
echo Fixing missing packages (openpyxl etc)...
if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv missing. Run 1-first-install bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install -e ".[ui]"
if errorlevel 1 (
  echo [FAILED] pip install
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -c "import openpyxl; print('openpyxl OK')"
if errorlevel 1 (
  echo [FAILED] openpyxl still missing
  pause
  exit /b 1
)
echo [OK] Now double-click the desktop shortcut again.
pause
exit /b 0