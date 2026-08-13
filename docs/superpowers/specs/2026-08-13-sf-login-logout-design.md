# Salesforce 로그인 / 로그아웃 UI — 설계 스펙

**날짜:** 2026-08-13  
**상태:** 설계 승인됨 (대화 합의)  
**대상:** 로컬 Streamlit 「설정」탭  
**관련:** `docs/superpowers/specs/2026-08-13-local-launcher-settings-design.md`, `src/ai_work_automation/sf/cli_status.py`, `src/ai_work_automation/webui.py`

## 1. 목표

설정 탭에서 Salesforce CLI 계정을 **로그인 · 로그아웃 · 전환**할 수 있게 한다.  
여러 org를 동시에 로그인해 두고 alias로 전환하거나, 특정 alias만 로그아웃한 뒤 다른 계정으로 다시 로그인할 수 있다.

성공 기준:

1. 「로그인」→ 브라우저 SF 로그인 → 목록/현재 상태에 Connected·username 표시
2. 다른 alias로 로그인 후 「이 계정 사용」→ `config/settings.yaml`의 `sf_org_alias` 갱신, 이후 SF 작업이 그 org 사용
3. 행 「로그아웃」→ 해당 alias만 제거/미연결, 다른 로그인 유지
4. VOC·출장보고 등 기존 탭 회귀 없음 (현재 alias만 바뀜)

## 2. 비목표

- Connected App / JWT / Client Credentials 등 앱 자체 OAuth
- UI 또는 `.env`에 `SF_ACCESS_TOKEN` / `SF_INSTANCE_URL` 저장 유도
- PowerShell 전용 로그인 마법사(bat)를 UX의 주경로로 두기
- 로그인 중 CLI 프로세스 강제 종료·커스텀 타임아웃 UI
- 팀 다중 사용자 프로필 / 원격 허브용 계정 전환

## 3. 접근 (확정)

**설정 탭에서 Salesforce CLI를 래핑**한다.

- 로그인: `sf org login web --alias <alias>`
- 로그아웃: `sf org logout --target-org <alias>`
- 목록: `sf org list --json`
- 현재 상태: 기존 `get_sf_cli_status(alias)` (`sf org display`)

토큰은 CLI가 관리한다. 앱은 alias·상태·버튼만 다룬다.

## 4. 사용 흐름

1. 사용자가 **설정** 탭을 연다.
2. **로그인된 org 목록**을 본다 (alias, username, Connected 여부).
3. **전환:** 행의 「이 계정 사용」→ 해당 alias를 현재 `sf_org_alias`로 저장하고 상태 갱신.
4. **새/다른 계정:** alias 입력칸에 원하는 alias를 넣고 「로그인」→ 브라우저에서 SF 로그인 → 목록 새로고침.
5. **로그아웃:** 목록 행의 「로그아웃」→ 확인 → CLI logout → 목록 새로고침. (현재 alias 전용 별도 버튼은 없음)
6. 「새로고침」으로 목록·현재 상태를 다시 조회한다.

## 5. UI (설정 탭 · Salesforce 블록)

기존 Salesforce CLI 영역을 확장한다.

| 요소 | 동작 |
|------|------|
| `sf_org_alias` 입력 | 기존과 동일. 「설정 저장」으로 yaml 반영 |
| 로그인된 org 목록 | `sf org list` 결과. 열: alias, username, connected |
| 「이 계정 사용」 | 행 alias → yaml `sf_org_alias` 저장 + session 상태 갱신 |
| 「로그인」 | 현재 alias(입력칸)로 `sf org login web`. 스피너 + 「브라우저에서 로그인하세요」 |
| 「로그아웃」 | 목록 각 행에 버튼. 확인 후 해당 alias logout |
| 「새로고침」 | 목록 + `get_sf_cli_status` 재조회 |

PMS 키·`field_report_root`·`dry_run` 등 기존 설정 항목은 변경하지 않는다.

## 6. 구성 요소

| 구성 | 역할 |
|------|------|
| `sf` CLI 헬퍼 (신규 함수, `cli_status.py` 확장 또는 인접 모듈) | `list_sf_orgs`, `login_sf_org`, `logout_sf_org`; 기존 status와 동일하게 subprocess + `--json` 패턴, 테스트용 runner 주입 |
| `webui.py` 설정 탭 | 목록·버튼·스피너·에러 표시; 토큰 미수집 |
| `config/settings.yaml` | `sf_org_alias`만 갱신 (「이 계정 사용」/설정 저장) |

### 6.1 CLI 명령

- 목록: `sf org list --json` → alias / username / connectedStatus(또는 동등 필드) 파싱
- 로그인: `sf org login web --alias <alias>` (브라우저; 프로세스 종료까지 대기). `--json`은 web 로그인 특성상 선택·환경에 따라 생략 가능하나, 성공/실패는 exit code·후속 `org list`/`org display`로 확인
- 로그아웃: `sf org logout --target-org <alias> --json`
- 현재 상태: 기존 `sf org display --target-org <alias> --json`

### 6.2 오류 처리

| 상황 | UI |
|------|-----|
| `sf` 미설치 | 기존 안내 (`1-처음설치.bat` / CLI 설치 URL / login 명령) |
| 로그인 취소·실패 | 에러 메시지; 목록 유지 |
| 로그아웃 실패 | 에러 + 새로고침 유도 |
| JSON 파싱 실패 | 짧은 에러 메시지 (stdout 일부만, 시크릿 없음) |
| 로그인 대기 | 스피너만; CLI 기본 대기. 앱에서 강제 kill/타임아웃 UI 없음 |

### 6.3 보안

- 비밀번호·액세스 토큰을 UI·로그·session_state에 저장하지 않음
- `.env` SF 토큰 경로를 권장하지 않음 (기존 정책 유지)
- 로컬 `127.0.0.1` 전제와 충돌 없음

## 7. 테스트

- **단위:** `list` / `login` / `logout` 헬퍼를 mock subprocess(또는 주입 runner)로 검증. 브라우저·실 org 불필요
- **수동:** 로그인 1회 + 「이 계정 사용」전환 1회 + 로그아웃 1회
- **회귀:** 설정 저장(PMS/yaml), 기존 탭이 현재 `sf_org_alias`만 쓰는지 스모크

## 8. 문서

구현 후 짧게 갱신:

- `00-여기부터-읽으세요.md` / `docs/local-app.md`: PowerShell 로그인만 필수가 아니라, 설정 탭 「로그인」으로도 가능하다고 안내
- 최초 설치 시 CLI 자동 설치는 기존 `first-install.ps1` 범위(본 스펙과 독립)

## 9. 구현 순서 (참고)

1. CLI 헬퍼 + 단위 테스트  
2. 설정 탭 UI (목록 · 로그인 · 로그아웃 · 이 계정 사용)  
3. 문서 한 줄 안내  
4. 수동 스모크
