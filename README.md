# AI 업무 자동화 CLI

이 프로젝트는 Case 옵트인을 관리하고, 선택된 Case에 대해 Salesforce와 PMS 연동 작업을 실행하는 CLI 도구입니다.

## 실행 방법

1. 가상환경을 만들고 의존성을 설치합니다.
   ```powershell
   python -m venv .venv
   .venv\Scripts\activate
   pip install -e ".[dev]"
   ```
2. 환경 예시를 복사해 값을 채웁니다.
   ```powershell
   Copy-Item .env.example .env
   Copy-Item config\settings.example.yaml config\settings.yaml
   ```
3. `config/settings.yaml`에서 `automation_enabled_after`, 경로, `pms_project_id`를 확인하고, `.env`에서 PMS 토큰을 설정합니다.

## Salesforce 인증

우선순위는 다음과 같습니다.

1. `.env`의 `SF_INSTANCE_URL` / `SF_ACCESS_TOKEN` 값이 있으면 그대로 사용
2. 없으면 로그인된 Salesforce CLI에서 자동으로 토큰을 가져옴 (`sf org display --target-org <sf_org_alias> --json`)

즉, 아래처럼 sf CLI에 로그인만 되어 있으면 `.env`에 Salesforce 값을 넣지 않아도 됩니다.

```powershell
sf org login web --alias parksystems
```

org 별칭이 다르면 `config/settings.yaml`의 `sf_org_alias`를 수정하세요. sf CLI 세션 토큰이 만료되면 위 로그인 명령을 다시 실행하면 됩니다.
4. Case를 선택하고 확인합니다. Case Id 대신 Case Number(예: 00173841)를 써도 됩니다.
   ```powershell
   ai-work select 00173841
   ai-work list-selected
   ```
5. 실행합니다.
   ```powershell
   ai-work run 00173841 --dry-run   # 시뮬레이션만 (등록될 내용 미리보기)
   ai-work run 00173841 --real      # 실제 등록 (등록 전 승인 질문)
   ai-work run 00173841 --type er   # PMS 이슈 타입 지정 (sr|er, 생략 시 제목으로 자동 추정)
   ```
   `--dry-run`/`--real`을 생략하면 `config/settings.yaml`의 `dry_run` 값을 따릅니다.

## 웹 UI

명령어 대신 브라우저 화면으로 쓰려면:

```powershell
pip install -e ".[ui]"
.venv\Scripts\streamlit.exe run src\ai_work_automation\webui.py
```

브라우저에서 http://localhost:8501 이 열립니다.

- **후보 스캔·등록** 탭: 컷오프 이후 VOC+SW 워크오더 목록(연동 여부 표시) → 워크오더 선택 → 미리보기(dry-run) → 내용 확인 후 실제 등록
- **PMS 이슈 상태** 탭: 옵트인된 케이스에 연결된 PMS 이슈들의 현재 상태 확인
- 바탕화면 아이콘으로 로컬만 띄우려면 [docs/local-app.md](docs/local-app.md) 참고

집 PC를 Tailscale 허브로 쓰고 재부팅 후 자동 기동하려면 [docs/hub-autostart.md](docs/hub-autostart.md) 참고.

## 유용한 명령

```powershell
ai-work scan     # 컷오프 이후 VOC+SW 워크오더 후보 나열 (연동/선택 여부 표시)
ai-work status   # 옵트인된 케이스의 PMS 이슈 상태 확인
```

## PMS 등록 동작

- 제목: 워크오더의 VOC Title(없으면 Case 제목)을 그대로 사용합니다.
- 타입: SR(문제/버그 신고, 트래커 1) / ER(개선·추가 요청, 트래커 2). 제목에 "요청/개선/추가"가 있으면 ER로 자동 추정하며 `--type`으로 지정할 수 있습니다.
- 후속 워크오더: 같은 Case의 다른 워크오더에 이미 PMS 이슈가 연결돼 있으면, 신규 이슈를 만들지 않고 그 이슈에 댓글을 추가합니다. 워크오더 Activities에는 `PMS – <이슈 URL> (댓글)` 형식으로 기록됩니다.
- 이미 Activities에 PMS 이슈 링크가 있는 워크오더는 건너뜁니다(중복 방지).

## 안전 규칙

- 선택되지 않은 Case는 실행하지 않습니다.
- `automation_enabled_after` 이전의 Case/Work Order는 쓰기 작업을 하지 않습니다.
- 외부 게시 전 Human Gate가 기본으로 동작합니다.
- 실제 비밀값은 커밋하지 마세요. `config/settings.yaml`은 로컬에서만 사용합니다.
