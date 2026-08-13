# 로컬 앱 (바탕화면 바로가기)

본인 PC에서 아이콘 한 번으로 Streamlit UI(`http://localhost:8501`)를 띄우는 방법입니다.  
Tailscale 허브(`0.0.0.0`)와는 **별도**입니다. 허브는 [docs/hub-autostart.md](hub-autostart.md) 참고.

**클린 PC / 처음 설치:** [local-app-first-run.md](local-app-first-run.md) 를 먼저 보세요.  
**명령이 어려우면:** [AI-설치요청-프롬프트.md](../AI-설치요청-프롬프트.md) 를 AI 채팅에 붙여 넣으세요.

## 1회 준비

저장소 루트에서:

```powershell
cd "C:\Users\shp09\Documents\01_AI Tool\AI 업무 자동화 Tool"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[ui]"
```

Salesforce CLI 로그인 (설정에 맞는 alias, 기본 `parksystems`):

```powershell
sf org login web --alias parksystems
```

설정 파일이 없으면 예시를 복사합니다:

```powershell
Copy-Item .env.example .env
Copy-Item config\settings.example.yaml config\settings.yaml
```
`.env`에 `PMS_API_KEY` 등을 넣거나, 앱의 **설정** 탭에서 나중에 저장해도 됩니다.

## 바로가기 등록

저장소 **최상위**에서 `등록-로컬앱.bat` 을 더블클릭합니다.

시작 메뉴에도 넣으려면:

```text
등록-로컬앱.bat -StartMenu
```

또는 PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-local-app-shortcut.ps1
powershell -ExecutionPolicy Bypass -File scripts\register-local-app-shortcut.ps1 -StartMenu
```

바탕화면에 **「AI 업무자동화」** 바로가기가 생깁니다.

## 사용

1. 바로가기를 더블클릭한다.
2. 수 초 후 브라우저에서 `http://localhost:8501`이 열린다.
3. **설정** 탭에서 PMS API 키·출장보고 경로·dry_run·SF org alias를 확인·저장한다.
4. SF가 미연결이면 안내에 따라 `sf org login` 후 다시 확인한다.

이미 서버가 떠 있으면 프로세스를 죽이지 않고 브라우저만 다시 엽니다.

## hub와 동시 사용 금지

로컬 런처와 hub(`scripts/start-hub-streamlit.ps1`, `0.0.0.0:8501`)는 **같은 포트 8501**을 씁니다.  
동시에 켜지 마세요. hub가 이미 Listen 중이면 로컬 런처는 그 리스너를 재사용하고 브라우저만 엽니다.

집 PC를 Tailscale 허브로 쓰는 경우는 [docs/hub-autostart.md](hub-autostart.md)만 사용하세요.

## 로그

- `logs/local-app.log` — 기동 이력
- `logs/local-app.out.log` / `.err.log` — Streamlit stdout/stderr

## 직접 실행 (바로가기 없이)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch-local-app.ps1
```
