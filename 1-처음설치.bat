@echo off
setlocal EnableExtensions
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo ============================================================
echo   AI 업무자동화 - 처음 설치 (ZIP / 클린 PC)
echo ============================================================
echo   이 창을 닫지 말고, 끝날 때까지 기다려 주세요.
echo ============================================================
echo.

REM --- 0) 위치 확인 ---
if not exist "%~dp0pyproject.toml" (
  echo [오류] 잘못된 폴더입니다.
  echo 00-여기부터-읽으세요.md 와 1-처음설치.bat 이 같은 폴더에 있어야 합니다.
  echo ZIP을 푼 안쪽 폴더로 이동한 뒤 다시 실행하세요.
  goto :END_FAIL
)

REM --- 1) Python ---
echo [1/5] Python 확인 중...
python --version >nul 2>&1
if errorlevel 1 (
  echo.
  echo [필요] Python이 없거나 PATH에 없습니다.
  echo 1^) https://www.python.org/downloads/ 에서 설치
  echo 2^) 설치 화면에서 "Add python.exe to PATH" 체크
  echo 3^) PC 재시작 후 이 bat을 다시 실행
  echo.
  start "" "https://www.python.org/downloads/"
  goto :END_FAIL
)
python --version
echo.

REM --- 2) venv ---
echo [2/5] 가상환경(.venv) 준비 중...
if not exist "%~dp0.venv\Scripts\python.exe" (
  python -m venv "%~dp0.venv"
  if errorlevel 1 (
    echo [오류] 가상환경 만들기에 실패했습니다.
    goto :END_FAIL
  )
) else (
  echo       이미 .venv 가 있어 재사용합니다.
)
echo.

REM --- 3) packages ---
echo [3/5] 프로그램 설치 중... ^(처음이면 몇 분 걸릴 수 있습니다^)
"%~dp0.venv\Scripts\python.exe" -m pip install -U pip
if errorlevel 1 (
  echo [오류] pip 업그레이드 실패
  goto :END_FAIL
)
"%~dp0.venv\Scripts\python.exe" -m pip install -e ".[ui]"
if errorlevel 1 (
  echo [오류] 패키지 설치 실패. 인터넷/회사망 정책을 확인하세요.
  goto :END_FAIL
)
echo.

REM --- 4) config files ---
echo [4/5] 설정 파일 복사 중...
if not exist "%~dp0.env" (
  if exist "%~dp0.env.example" (
    copy /Y "%~dp0.env.example" "%~dp0.env" >nul
    echo       .env 생성
  )
) else (
  echo       .env 이미 있음
)
if not exist "%~dp0config\settings.yaml" (
  if exist "%~dp0config\settings.example.yaml" (
    copy /Y "%~dp0config\settings.example.yaml" "%~dp0config\settings.yaml" >nul
    echo       config\settings.yaml 생성
  )
) else (
  echo       settings.yaml 이미 있음
)
echo.

REM --- 5) shortcut ---
echo [5/5] 바탕화면 바로가기 등록 중...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\register-local-app-shortcut.ps1"
if errorlevel 1 (
  echo [경고] 바로가기 등록 실패. 나중에 등록-로컬앱.bat 을 다시 실행하세요.
) else (
  echo       바탕화면에 "AI 업무자동화" 바로가기를 만들었습니다.
)
echo.

echo ============================================================
echo   자동 설치 단계가 끝났습니다.
echo ============================================================
echo.
echo   다음으로 "직접" 한 가지만 하세요 (Salesforce 로그인):
echo.
echo   1. Windows 키 -^> PowerShell 실행
echo   2. 아래 한 줄을 붙여넣고 Enter:
echo.
echo      sf org login web --alias parksystems
echo.
echo   3. 브라우저에서 회사 계정으로 로그인
echo   4. 바탕화면 "AI 업무자동화" 아이콘 더블클릭
echo.
echo   자세한 그림/설명: 00-여기부터-읽으세요.md
echo   Salesforce CLI가 없으면:
echo      https://developer.salesforce.com/tools/salesforcecli
echo.
goto :END_OK

:END_FAIL
echo.
echo [중단] 문제를 고친 뒤 1-처음설치.bat 을 다시 실행하세요.
echo 가이드: 00-여기부터-읽으세요.md
pause
exit /b 1

:END_OK
pause
exit /b 0
