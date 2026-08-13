# 로컬 런처 + Streamlit 설정 UI — 설계 스펙

**날짜:** 2026-08-13  
**상태:** 설계 승인됨 (2026-08-13)  
**대상 사용자:** 본인(Ethan) 전용  
**관련:** `docs/hub-autostart.md`, `scripts/start-hub-streamlit.ps1`, `src/ai_work_automation/webui.py`

## 1. 목표

아이콘 한 번으로 로컬 Streamlit 서버를 띄우고 브라우저를 연다.  
PMS API 키·출장보고 경로 등 자주 쓰는 값은 `.env` / `settings.yaml`을 직접 편집하지 않고 UI에서 저장한다.

성공 기준:

1. 바탕화면(또는 시작 메뉴) 아이콘 더블클릭 → 수 초 내 `http://localhost:8501` 오픈
2. 설정 UI에서 PMS 키 저장 → 앱 재시작 후에도 PMS 호출에 반영
3. SF는 CLI 연결 상태를 보여주고, 미연결 시 재로그인 안내
4. 기존 CLI·webui 워크플로(스캔, 출장보고, 메일 등)는 회귀 없음

## 2. 비목표 (이번 범위 밖)

- 설치형 `.exe` / 네이티브 런처 창 / 시스템 트레이 상주 앱
- Tailscale 허브·`0.0.0.0` 바인딩 (기존 hub 스크립트는 그대로 유지, 로컬 런처와 분리)
- Salesforce Connected App JWT / Client Credentials 및 앱 자체 토큰 갱신 서버
- 팀원용 설치 마법사·자동 업데이트·다중 사용자 설정 프로필

## 3. 접근 (확정)

**바탕화면 바로가기 + Streamlit 설정 탭** (네이티브 앱 없음).

대안이었던 작은 런처 창·PyInstaller exe는 본인 전용 범위에서 유지비 대비 이득이 적어 채택하지 않는다.

## 4. 사용 흐름

1. 사용자가 **「AI 업무자동화」** 바로가기를 실행한다.
2. `scripts/launch-local-app.ps1`이 `127.0.0.1:8501`에서 Streamlit을 기동한다.
   - 이미 Listen 중이면 프로세스를 죽이지 않고 재사용한다.
3. 기본 브라우저로 `http://localhost:8501`을 연다.
4. 사용자는 메인 화면의 **「설정」탭**에서 시크릿·경로를 확인하고 필요 시 저장한다.
5. SF 미연결이면 안내 문구와 `sf org login web --alias <sf_org_alias>` 안내를 본다.
6. 서버 중지는 1차 범위에서 **구현하지 않는다**. PC 종료·작업 관리자·포트 정리로 충분하다.

## 5. 구성 요소

| 구성 | 역할 |
|------|------|
| `scripts/launch-local-app.ps1` | 로컬 전용 기동: address=`127.0.0.1`, port=`8501`, 한글/공백 경로 short path, 브라우저 오픈, 이미 떠 있으면 재사용 |
| `scripts/register-local-app-shortcut.ps1` | 바탕화면 `.lnk` 생성(시작 메뉴는 선택 플래그). 대상=`launch-local-app.ps1`, WorkingDirectory=repo |
| Streamlit 설정 UI | `webui.py`에 **「설정」탭** 추가 |
| 설정 저장 헬퍼 | `.env` 키 upsert, `settings.yaml` 부분 갱신. 기존 키/주석을 불필요하게 지우지 않도록 최소 변경 |

기존 `start-hub-streamlit.ps1` / `register-hub-autostart.ps1`는 **허브(Tailscale)용으로 유지**한다. 로컬 런처와 역할을 섞지 않는다.

## 6. 설정 항목·저장 위치

| UI 항목 | 저장 | 동작 |
|---------|------|------|
| PMS API Key | `.env` → `PMS_API_KEY` | password 입력. 저장 후 값은 다시 전체 표시하지 않음. 「저장됨/미설정」뱃지 |
| field_report_root | `config/settings.yaml` | 경로 문자열. 존재 여부 힌트(폴더 있음/없음) |
| dry_run | `config/settings.yaml` | 토글 |
| sf_org_alias | `config/settings.yaml` | 텍스트(기본 `parksystems`) |
| SF 연결 상태 | 저장 없음 | `sf org display --target-org <alias> --json` 결과로 Connected/오류 표시 |
| SF_INSTANCE_URL / SF_ACCESS_TOKEN | UI에서 받지 않음 | CLI 토큰 경로 유지. `.env`에 고정 토큰을 넣도록 유도하지 않음 |

스캔 필터 등 이미 사이드바에 있는 항목은 기존 UX를 유지한다. 이번 스펙에서 필수로 옮기지 않는다.

### 6.1 저장 후 반영

- `.env` 저장 직후: `os.environ["PMS_API_KEY"]`를 갱신하고, 이후 PMS 클라이언트 생성 시 새 값을 쓰게 한다.
- `settings.yaml` 저장 직후: 다음 `load_settings(SETTINGS_PATH)` 호출이 새 값을 읽게 한다(캐시가 있으면 무효화).
- Streamlit 전체 프로세스 재시작은 요구하지 않는다(가능하면 저장 즉시 반영).

### 6.2 보안

- `.env`는 기존처럼 gitignore.
- API 키 위젯은 `type="password"`.
- 로그/에러 메시지에 키 전문을 출력하지 않는다.
- 바인딩은 `127.0.0.1`만 (로컬 런처).

## 7. 런처 동작 상세

`launch-local-app.ps1`:

- Repo root = 스크립트 기준 상위.
- `.venv\Scripts\python.exe` 및 `src\ai_work_automation\webui.py` 존재 검사. 없으면 한국어 안내 후 종료.
- `Get-NetTCPConnection -LocalPort 8501 -State Listen`이 있으면 Start-Process 생략.
- 없으면 `python -m streamlit run … --server.address=127.0.0.1 --server.port=8501 --server.headless=true` (short path 패턴은 hub 스크립트와 동일).
- 기동 후 짧게 대기·Listen 확인 후 `Start-Process`로 브라우저 URL 오픈.
- 로그: `logs/local-app.log` (선택, hub 로그와 파일명 분리).

바로가기:

- 이름: `AI 업무자동화`
- 대상: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "…\launch-local-app.ps1"`
- 아이콘: 저장소 내 아이콘 파일이 있으면 사용, 없으면 PowerShell/Streamlit 기본 아이콘도 허용(1차).

## 8. 오류·경계

| 상황 | 처리 |
|------|------|
| venv 없음 | 런처가 설치 명령 안내 후 exit 1 |
| 포트는 열렸으나 응답 없음 | 수 초 재시도 후 브라우저 오픈 + 로그에 WARNING |
| SF CLI 없음/미로그인 | 설정 UI에 오류·재로그인 명령 표시. 앱 기동 자체는 막지 않음 |
| `.env` / yaml 쓰기 실패 | UI에 에러, 파일 미변경 또는 원자적 쓰기 실패 시 롤백 |
| hub(0.0.0.0)와 동시 기동 | 동일 포트 충돌. 문서에 “한 번에 하나만” 명시. 로컬 런처는 이미 Listen이면 재사용만 함 |

## 9. 테스트

- 수동: 아이콘 → 브라우저, 두 번째 클릭 시 중복 프로세스 없이 재오픈
- 수동: PMS 키 저장 → UI에서 PMS 동작 확인 → 프로세스 재시작 후에도 유지
- 수동: `field_report_root` 변경 반영
- 자동(가능 시): 설정 헬퍼 unit test — `.env` upsert가 다른 키를 지우지 않음, yaml 부분 갱신이 스키마를 깨지 않음

## 10. 구현 순서 (참고)

1. 설정 저장 헬퍼 + 테스트
2. webui 설정 UI
3. `launch-local-app.ps1`
4. 바로가기 등록 스크립트 + README/`docs` 한 절 안내
