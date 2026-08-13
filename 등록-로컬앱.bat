@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo === AI 업무자동화 - 바탕화면 바로가기 등록 ===
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\register-local-app-shortcut.ps1" %*
if errorlevel 1 (
  echo.
  echo [실패] 바로가기 등록에 실패했습니다.
  echo 가이드: docs\local-app-first-run.md
  pause
  exit /b 1
)

echo.
echo [완료] 바탕화면에 "AI 업무자동화" 바로가기가 생겼습니다.
echo.
echo 클린 PC 최초 설치는 아래 문서를 순서대로 따라 하세요:
echo   docs\local-app-first-run.md
echo.
echo 시작 메뉴에도 넣으려면:
echo   등록-로컬앱.bat -StartMenu
echo.
pause
endlocal
