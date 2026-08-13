# 클린 PC 최초 실행 가이드

새 Windows PC(또는 이 저장소를 처음 받는 PC)에서 **로컬 앱**을 쓰기까지의 순서입니다.  
목표: 바탕화면 **「AI 업무자동화」** 아이콘 → `http://localhost:8501`

상세·일상 사용은 [local-app.md](local-app.md) 참고.

---

## GitHub ZIP으로 받은 직후 (초보 추천)

전문 용어 없이 **클릭 순서만** 적어 둔 문서:

→ 저장소 루트 **[00-여기부터-읽으세요.md](../00-여기부터-읽으세요.md)**  
→ 같은 폴더 **[1-처음설치.bat](../1-처음설치.bat)** 더블클릭

README나 이 문서의 아래쪽(파이썬 명령 등)은 **나중에** 보면 됩니다.

**설치를 직접 하기 어렵다면 → [아래 「AI에게 맡기기」](#ai에게-맡기기-추천)를 보세요.**

---

## AI에게 맡기기 (추천)

명령어·환경 구축을 잘 모를 때, Claude / ChatGPT / Gemini / Cursor 같은 AI에게 **이 폴더를 통째로** 맡기고 설치를 진행하게 할 수 있습니다.

### 진행 절차

1. **이 저장소 폴더**를 AI에 연결합니다.
   - **Cursor:** File → Open Folder로 이 폴더를 연 뒤, Agent/Chat 사용
   - **Claude / ChatGPT / Gemini 등:** 프로젝트·채팅에 이 폴더(또는 zip)를 첨부·업로드. 가능하면 로컬 폴더 연동을 사용
2. 저장소 루트의 [`AI-설치요청-프롬프트.md`](../AI-설치요청-프롬프트.md) 를 엽니다.
3. 문서 안의 **「복사 구간」** 전체를 복사해 AI 채팅에 붙여 넣습니다.
4. AI가 안내하는 대로 **한 단계씩** 따릅니다.
   - AI가 터미널을 실행할 수 있으면: 가상환경·패키지·바로가기까지 대부분 자동
   - 사용자가 직접 해야 하는 것: Python/`sf` 설치 마법사, Salesforce 브라우저 로그인, PMS API 키 입력(앱 **설정** 탭)
5. 끝나면 바탕화면 **「AI 업무자동화」** 를 더블클릭해 `http://localhost:8501` 이 열리는지 확인합니다.
6. 앱 **설정** 탭에서 PMS 키·DFS2 경로를 저장하고, **SF 상태 새로고침**으로 Connected를 확인합니다.

### AI 사용 시 주의

| 해도 됨 | 하지 말 것 |
|---------|------------|
| 폴더 첨부 + 위 프롬프트 사용 | 채팅에 PMS/SF **토큰 전문**을 붙여 넣기 |
| AI가 제안한 `pip` / `venv` / `등록-로컬앱.bat` 실행 | AI가 `.env`에 `SF_ACCESS_TOKEN`을 넣으라고 하면 → **거절** (CLI 로그인 사용) |
| 오류 메시지를 AI에게 그대로 보여 주기 | 잘 모르는 채 `git push --force` 등 실행 |

직접 손으로 설치하려면 아래 0절부터 따라가면 됩니다.

---

## 0. 준비물 체크

| 항목 | 확인 |
|------|------|
| Windows 10/11 | Outlook·Excel COM(메일·출장보고)용 |
| 이 저장소 폴더 | Git clone 또는 OneDrive/복사본 |
| 인터넷 | `pip` / Salesforce 로그인용 |
| (선택) PMS API Key | 설정 탭 또는 `.env`에 입력 |
| (출장보고 시) OneDrive DFS2 경로 | `field_report_root`로 지정 |

---

## 1. 필수 프로그램 설치

### 1-1. Python 3.11 이상

1. [python.org](https://www.python.org/downloads/)에서 Windows 설치
2. 설치 화면에서 **Add python.exe to PATH** 체크
3. 확인:

```powershell
python --version
```

### 1-2. Salesforce CLI (`sf`)

1. [Salesforce CLI 설치](https://developer.salesforce.com/tools/salesforcecli)
2. 확인:

```powershell
sf version
```

### 1-3. (메일·출장보고 PNG 시) Outlook

회사 계정으로 Outlook을 한 번 이상 실행·로그인합니다.  
미설치여도 **설정·스캔 UI**는 동작할 수 있으나, Outlook 메일 초안은 불가합니다.

---

## 2. 저장소에서 가상환경·UI 설치

PowerShell에서 **저장소 루트**(이 폴더)로 이동합니다.

```powershell
cd "C:\경로\AI 업무 자동화 Tool"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e ".[ui]"
```

실패 시: PATH의 `python`이 3.11+인지, 회사 프록시/`pip` 권한을 확인합니다.

---

## 3. 설정 파일 복사

```powershell
Copy-Item .env.example .env
Copy-Item config\settings.example.yaml config\settings.yaml
```

| 파일 | 최초에 할 일 |
|------|----------------|
| `.env` | `PMS_API_KEY`는 비워 둬도 됨 → 나중에 앱 **설정** 탭에서 저장 가능. **`SF_ACCESS_TOKEN`은 넣지 말 것**(만료·갱신 문제). |
| `config/settings.yaml` | `sf_org_alias`(기본 `parksystems`), 필요 시 `field_report_root`(DFS2 OneDrive 경로), `dry_run` 확인 |

---

## 4. Salesforce 로그인 (토큰 자동 갱신의 핵심)

```powershell
sf org login web --alias parksystems
sf org display --target-org parksystems
```

`connectedStatus: Connected`이면 성공입니다.  
이후 앱이 필요할 때마다 CLI에서 액세스 토큰을 가져옵니다. 만료·오류 시 같은 `login`을 다시 실행하세요.

---

## 5. 바탕화면 바로가기 등록

저장소 **최상위**에서 더블클릭:

```text
등록-로컬앱.bat
```

또는:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register-local-app-shortcut.ps1
```

시작 메뉴에도:

```text
등록-로컬앱.bat -StartMenu
```

바탕화면에 **「AI 업무자동화」** 가 생기면 성공입니다.

---

## 6. 첫 실행·설정 탭

1. **「AI 업무자동화」** 더블클릭
2. 브라우저가 `http://localhost:8501` 을 연다 (수 초 소요)
3. **설정** 탭에서:
   - **PMS API Key** 입력 후 저장
   - **field_report_root** (DFS2 폴더 경로) 저장
   - **dry_run** / **sf_org_alias** 확인
   - **SF 상태 새로고침** → Connected 확인

연결이 안 되면 `sf org login web --alias parksystems` 후 다시 새로고침합니다.

---

## 7. 자주 나오는 문제

| 증상 | 조치 |
|------|------|
| 바로가기 클릭 후 아무 창도 없음 | `logs\local-app.err.log` 확인. `.venv` 설치(2절) 다시 실행 |
| `python` / `sf` 명령을 찾을 수 없음 | PATH 재설치 후 **새** PowerShell에서 재시도 |
| 포트 오류·페이지 안 열림 | 다른 Streamlit/허브가 8501 사용 중인지 확인. **허브와 로컬은 동시에 쓰지 말 것** |
| SF 인증 오류 | `sf org login web --alias parksystems` 재실행. `.env`의 오래된 `SF_ACCESS_TOKEN` 삭제 |
| 한글 경로 오류 | 반드시 `등록-로컬앱.bat` / `launch-local-app.ps1` 사용 (short path 처리) |

---

## 8. 체크리스트 (복사용)

- [ ] Python 3.11+ / PATH
- [ ] Salesforce CLI (`sf`)
- [ ] `python -m venv .venv` + `pip install -e ".[ui]"`
- [ ] `.env` / `settings.yaml` 복사
- [ ] `sf org login web --alias parksystems`
- [ ] `등록-로컬앱.bat` 실행 → 바탕화면 아이콘
- [ ] 아이콘 → localhost:8501 → **설정** 탭에서 PMS·경로·SF 확인

**(대안)** AI에게 맡긴 경우: [`AI-설치요청-프롬프트.md`](../AI-설치요청-프롬프트.md) 복사 → AI 진행 → 아이콘·설정 탭만 확인

끝. 이후에는 아이콘만 더블클릭하면 됩니다.
