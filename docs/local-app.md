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

Salesforce CLI는 `1-처음설치.bat`가 없으면 자동 설치를 시도합니다.  
로그인은 한 번만 직접 (설정에 맞는 alias, 기본 `parksystems`):

앱을 연 뒤 **설정** 탭의 「로그인」으로도 같은 브라우저 로그인을 할 수 있습니다.  
로그인된 org **목록**에서 「이 계정 사용」으로 현재 alias를 바꾸고, 행의 「로그아웃」으로 해당 org만 끊을 수 있습니다.  
아래 PowerShell 명령은 백업 경로입니다.

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
4. SF가 미연결이면 **설정** 탭의 「로그인」으로 브라우저 로그인한 뒤 다시 확인한다.
5. **VOC 작성** 탭: Quill에 붙여넣거나 이미지를 업로드한다. 업로드 후 expander에서 left/top/right/bottom으로 선택 크롭한다. 결과는 PMS 본문(base64 `<img>`)과 SF Case/WO 파일 첨부(best-effort)에 들어간다. 크롭은 기존 `Pillow`(ui extra) 슬라이더이며 `streamlit-cropper`는 쓰지 않는다.

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
