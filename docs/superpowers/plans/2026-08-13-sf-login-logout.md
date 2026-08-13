# SF Login / Logout UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Streamlit 「설정」탭에서 Salesforce CLI org를 목록 조회·브라우저 로그인·행별 로그아웃·「이 계정 사용」으로 alias 전환한다.

**Architecture:** `sf/cli_status.py`에 list/login/logout 헬퍼를 추가하고(기존 status와 동일하게 runner 주입), `webui.py` 설정 탭 Salesforce 블록만 확장한다. 토큰은 CLI가 보관하며 UI는 alias·상태만 다룬다.

**Tech Stack:** Python 3.11+, Streamlit, Salesforce CLI (`sf`), pytest

**Spec:** `docs/superpowers/specs/2026-08-13-sf-login-logout-design.md`

## Global Constraints

- SF 토큰/비밀번호를 UI·로그·`session_state`·`.env`에 저장·유도하지 않음
- 로그인: `sf org login web --alias <alias>` (브라우저; 앱에서 kill/타임아웃 UI 없음)
- 로그아웃: `sf org logout --target-org <alias>` (목록 **행별**만; 현재 alias 전용 별도 버튼 없음)
- 「이 계정 사용」→ `update_settings_yaml(..., {"sf_org_alias": ...})` 로 yaml 갱신
- Connected App / JWT / 앱 자체 OAuth 금지
- PMS·`field_report_root`·`dry_run` UI는 변경하지 않음
- TDD: 헬퍼는 테스트 먼저; **커밋 Step은 사용자가 요청하기 전까지 건너뜀**
- Windows 로컬 앱 전제 (`127.0.0.1`)

## File map

| File | Responsibility |
|------|----------------|
| `src/ai_work_automation/sf/cli_status.py` | 기존 status + `list_sf_orgs` / `login_sf_org` / `logout_sf_org` |
| `tests/test_sf_cli_status.py` | list/login/logout 단위 테스트 추가 |
| `src/ai_work_automation/webui.py` | 설정 탭 Salesforce 블록 UI |
| `00-여기부터-읽으세요.md` | 설정 탭 로그인 안내 한 줄 |
| `docs/local-app.md` | 동일 안내 |

---

### Task 1: `list_sf_orgs` + `logout_sf_org`

**Files:**
- Modify: `src/ai_work_automation/sf/cli_status.py`
- Test: `tests/test_sf_cli_status.py`

**Interfaces:**
- Consumes: 기존 `_run_sf_json_subprocess`, `SfCliStatusError`
- Produces:
  - `@dataclass(frozen=True) class SfOrgRow: alias: str; username: str | None; connected: bool`
  - `list_sf_orgs(run_sf_command: Callable[[list[str]], dict[str, Any]] | None = None) -> list[SfOrgRow]`
  - `logout_sf_org(org_alias: str, run_sf_command: Callable[[list[str]], dict[str, Any]] | None = None) -> None`  
    — 성공 시 return; CLI `status != 0` 또는 runner가 `SfCliStatusError`면 `SfCliStatusError` raise

- [ ] **Step 1: Write failing tests**

`tests/test_sf_cli_status.py`에 추가:

```python
from ai_work_automation.sf.cli_status import (
    SfCliStatusError,
    get_sf_cli_status,
    list_sf_orgs,
    logout_sf_org,
)


def test_list_sf_orgs_flattens_non_scratch_and_sandboxes() -> None:
    def fake(args: list[str]) -> dict:
        assert args == ["org", "list"]
        return {
            "status": 0,
            "result": {
                "nonScratchOrgs": [
                    {
                        "alias": "parksystems",
                        "username": "a@example.com",
                        "connectedStatus": "Connected",
                    }
                ],
                "sandboxes": [
                    {
                        "alias": "sbx",
                        "username": "b@example.com",
                        "connectedStatus": "Disconnected",
                    }
                ],
                "other": [],
            },
        }

    rows = list_sf_orgs(run_sf_command=fake)
    assert len(rows) == 2
    assert rows[0].alias == "parksystems"
    assert rows[0].username == "a@example.com"
    assert rows[0].connected is True
    assert rows[1].alias == "sbx"
    assert rows[1].connected is False


def test_list_sf_orgs_skips_entries_without_alias_uses_username_as_fallback_alias() -> None:
    def fake(_args: list[str]) -> dict:
        return {
            "status": 0,
            "result": {
                "nonScratchOrgs": [
                    {"username": "only@example.com", "connectedStatus": "Connected"},
                ]
            },
        }

    rows = list_sf_orgs(run_sf_command=fake)
    assert len(rows) == 1
    assert rows[0].alias == "only@example.com"
    assert rows[0].username == "only@example.com"


def test_list_sf_orgs_cli_status_error() -> None:
    def fake(_args: list[str]) -> dict:
        return {"status": 1, "message": "list failed"}

    try:
        list_sf_orgs(run_sf_command=fake)
        assert False, "expected SfCliStatusError"
    except SfCliStatusError as exc:
        assert "list failed" in str(exc)


def test_logout_sf_org_ok() -> None:
    calls: list[list[str]] = []

    def fake(args: list[str]) -> dict:
        calls.append(args)
        return {"status": 0, "result": {}}

    logout_sf_org("parksystems", run_sf_command=fake)
    assert calls == [["org", "logout", "--target-org", "parksystems"]]


def test_logout_sf_org_raises_on_failure() -> None:
    def fake(_args: list[str]) -> dict:
        return {"status": 1, "message": "not logged in"}

    try:
        logout_sf_org("x", run_sf_command=fake)
        assert False, "expected SfCliStatusError"
    except SfCliStatusError as exc:
        assert "not logged in" in str(exc)
```

- [ ] **Step 2: Run tests — expect FAIL**

Run:

```powershell
python -m pytest tests/test_sf_cli_status.py -v
```

Expected: FAIL — `list_sf_orgs` / `logout_sf_org` import or AttributeError.

- [ ] **Step 3: Implement**

`cli_status.py`에 추가 (기존 `_run_sf_json_subprocess` / `get_sf_cli_status` 유지):

```python
@dataclass(frozen=True)
class SfOrgRow:
    alias: str
    username: str | None
    connected: bool


def _org_rows_from_list_result(result: object) -> list[SfOrgRow]:
    rows: list[SfOrgRow] = []
    if not isinstance(result, dict):
        return rows
    for value in result.values():
        if not isinstance(value, list):
            continue
        for item in value:
            if not isinstance(item, dict):
                continue
            username = item.get("username")
            alias_raw = item.get("alias") or username
            if not alias_raw:
                continue
            status = str(item.get("connectedStatus") or "")
            rows.append(
                SfOrgRow(
                    alias=str(alias_raw),
                    username=str(username) if username else None,
                    connected=status.lower() == "connected",
                )
            )
    return rows


def list_sf_orgs(
    run_sf_command: Callable[[list[str]], dict[str, Any]] | None = None,
) -> list[SfOrgRow]:
    runner = run_sf_command or _run_sf_json_subprocess
    data = runner(["org", "list"])
    if data.get("status") != 0:
        raise SfCliStatusError(str(data.get("message") or data)[:200])
    return _org_rows_from_list_result(data.get("result"))


def logout_sf_org(
    org_alias: str,
    run_sf_command: Callable[[list[str]], dict[str, Any]] | None = None,
) -> None:
    runner = run_sf_command or _run_sf_json_subprocess
    data = runner(["org", "logout", "--target-org", org_alias])
    if data.get("status") != 0:
        raise SfCliStatusError(str(data.get("message") or data)[:200])
```

Note: `_run_sf_json_subprocess`는 args 뒤에 `--json`을 붙이므로 호출 인자에 `--json`을 넣지 않는다.

- [ ] **Step 4: Run tests — expect PASS**

```powershell
python -m pytest tests/test_sf_cli_status.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit** (사용자 요청 시에만)

```bash
git add src/ai_work_automation/sf/cli_status.py tests/test_sf_cli_status.py
git commit -m "feat(sf): list and logout helpers for settings UI"
```

---

### Task 2: `login_sf_org`

**Files:**
- Modify: `src/ai_work_automation/sf/cli_status.py`
- Test: `tests/test_sf_cli_status.py`

**Interfaces:**
- Produces:
  - `login_sf_org(org_alias: str, run_sf_login: Callable[[list[str]], int] | None = None) -> None`  
    — 기본 구현: `sf org login web --alias <alias>`를 **`--json` 없이** 실행(브라우저). `returncode != 0`이면 `SfCliStatusError`.  
    — 테스트는 `run_sf_login`으로 exit code만 주입.

- [ ] **Step 1: Write failing tests**

```python
def test_login_sf_org_ok() -> None:
    calls: list[list[str]] = []

    def fake_login(args: list[str]) -> int:
        calls.append(args)
        return 0

    login_sf_org("parksystems", run_sf_login=fake_login)
    assert calls == [["org", "login", "web", "--alias", "parksystems"]]


def test_login_sf_org_raises_on_nonzero() -> None:
    def fake_login(_args: list[str]) -> int:
        return 1

    try:
        login_sf_org("x", run_sf_login=fake_login)
        assert False, "expected SfCliStatusError"
    except SfCliStatusError as exc:
        assert "login" in str(exc).lower() or "x" in str(exc)
```

Import에 `login_sf_org` 추가.

- [ ] **Step 2: Run tests — expect FAIL**

```powershell
python -m pytest tests/test_sf_cli_status.py::test_login_sf_org_ok tests/test_sf_cli_status.py::test_login_sf_org_raises_on_nonzero -v
```

Expected: FAIL (not defined).

- [ ] **Step 3: Implement**

```python
def _run_sf_login_subprocess(args: list[str]) -> int:
    exe = shutil.which("sf")
    if exe is None:
        raise SfCliStatusError(
            "Salesforce CLI(sf)를 찾을 수 없습니다. "
            "`1-처음설치.bat`를 다시 실행하거나 "
            "https://developer.salesforce.com/tools/salesforcecli 에서 설치한 뒤 "
            "`sf org login web --alias parksystems` 로 로그인하세요."
        )
    proc = subprocess.run(
        [exe, *args],
        text=True,
        encoding="utf-8",
    )
    return int(proc.returncode)


def login_sf_org(
    org_alias: str,
    run_sf_login: Callable[[list[str]], int] | None = None,
) -> None:
    runner = run_sf_login or _run_sf_login_subprocess
    code = runner(["org", "login", "web", "--alias", org_alias])
    if code != 0:
        raise SfCliStatusError(
            f"Salesforce 로그인에 실패했습니다 (alias={org_alias}, exit={code}). "
            "브라우저에서 로그인했는지 확인하세요."
        )
```

`subprocess` / `shutil`는 파일에 이미 import되어 있음.

- [ ] **Step 4: Run tests — expect PASS**

```powershell
python -m pytest tests/test_sf_cli_status.py -v
```

Expected: all PASS.

- [ ] **Step 5: Commit** (사용자 요청 시에만)

```bash
git add src/ai_work_automation/sf/cli_status.py tests/test_sf_cli_status.py
git commit -m "feat(sf): login_sf_org web login helper"
```

---

### Task 3: Settings tab UI — list / login / logout / use account

**Files:**
- Modify: `src/ai_work_automation/webui.py` — `_render_settings_tab` 내 `st.subheader("Salesforce CLI")` 블록 (대략 1337–1351행 부근; 함수명/행은 현재 파일 기준으로 검색)

**Interfaces:**
- Consumes: `list_sf_orgs`, `login_sf_org`, `logout_sf_org`, `get_sf_cli_status`, `update_settings_yaml`, `SETTINGS_PATH`
- Produces: UI only (no new public Python API)

- [ ] **Step 1: Replace Salesforce CLI block**

기존:

- 「SF 상태 새로고침」
- status success/warning/error
- `st.code("sf org login web ...")`
- caption

를 아래로 교체한다. import를 확장:

```python
from ai_work_automation.sf.cli_status import (
    SfCliStatusError,
    get_sf_cli_status,
    list_sf_orgs,
    login_sf_org,
    logout_sf_org,
)
```

UI 로직 (동일 `alias = org_alias.strip() or s.sf_org_alias` 사용):

1. **버튼 행:** 「새로고침」(`settings_sf_refresh`) — `list_sf_orgs()` 결과를 `st.session_state["sf_org_rows"]`에, `get_sf_cli_status(alias)`를 `st.session_state["sf_cli_status"]`에 저장. `SfCliStatusError`는 `st.session_state["sf_cli_action_error"] = str(exc)` 후 목록은 비우지 않으려면 이전 rows 유지(최초면 빈 리스트).
2. **현재 상태** — 기존과 동일하게 `sf_cli_status` 표시. 없으면 「새로고침을 눌러…」 info.
3. **「로그인」** (`settings_sf_login`) — `st.spinner("브라우저에서 Salesforce에 로그인하세요…")` 안에서 `login_sf_org(alias)`. 성공 시 success + list/status 재조회 + `st.rerun()`. `SfCliStatusError` → `st.error`.
4. **org 목록** — `rows = st.session_state.get("sf_org_rows")`. `None`이면 caption「새로고침으로 목록을 불러오세요」. 빈 리스트면「로그인된 org 없음」. 있으면 각 row에 대해 `st.columns`로 alias / username / Connected여부 / 「이 계정 사용」 / 「로그아웃」.
5. **「이 계정 사용」** (`settings_sf_use_{row.alias}` — alias에 특수문자 있으면 `hash` 또는 `re.sub`로 key 안전하게):
   - `update_settings_yaml(SETTINGS_PATH, {"sf_org_alias": row.alias})`
   - success + `st.rerun()` (입력칸이 새 settings를 읽도록)
6. **「로그아웃」** 확인 패턴:
   - 클릭 시 `st.session_state["sf_logout_pending"] = row.alias`
   - `sf_logout_pending`이 해당 alias면 「정말 로그아웃할까요?」 + 「확인」/`settings_sf_logout_ok_{safe}` + 「취소」/`settings_sf_logout_cancel`
   - 확인: `logout_sf_org(pending)` → pending clear → list/status refresh → `st.rerun()`
   - 취소: pending clear + `st.rerun()`
7. **에러 배너:** `sf_cli_action_error`가 있으면 `st.error` 후 표시한 뒤 키 삭제(또는 다음 성공 시 삭제).
8. **제거:** 필수로 보여 주던 `st.code(sf org login web…)` 는 로그인 버튼이 대체. caption은 「토큰은 UI에 저장하지 않습니다. CLI 로그인을 사용합니다.」 정도만 유지.

헬퍼(같은 함수 내부 nested 또는 블록 직전):

```python
def _refresh_sf_session(current_alias: str) -> None:
    try:
        st.session_state["sf_org_rows"] = list_sf_orgs()
        st.session_state["sf_cli_action_error"] = None
    except SfCliStatusError as exc:
        st.session_state["sf_cli_action_error"] = str(exc)
    st.session_state["sf_cli_status"] = get_sf_cli_status(current_alias)
```

로그인/로그아웃/새로고침 후 `_refresh_sf_session(alias)` 호출.

- [ ] **Step 2: Syntax / import smoke**

```powershell
.venv\Scripts\python.exe -c "from ai_work_automation.sf.cli_status import list_sf_orgs, login_sf_org, logout_sf_org; print('ok')"
python -m pytest tests/test_sf_cli_status.py -v
```

Expected: `ok` + tests PASS. (Streamlit UI는 수동)

- [ ] **Step 3: Manual smoke (구현 PC에 `sf` 있을 때)**

1. 앱 설정 탭 → 새로고침 → 목록 표시  
2. 로그인(이미 되어 있으면 skip)  
3. 「이 계정 사용」→ yaml `sf_org_alias` 변경 확인  
4. 테스트용 여분 alias가 있으면 로그아웃 1회  

- [ ] **Step 4: Commit** (사용자 요청 시에만)

```bash
git add src/ai_work_automation/webui.py
git commit -m "feat(webui): SF login, logout, and org switch in settings"
```

---

### Task 4: Docs one-liners

**Files:**
- Modify: `00-여기부터-읽으세요.md`
- Modify: `docs/local-app.md`

**Interfaces:** none (docs only)

- [ ] **Step 1: Update beginner guide**

`00-여기부터-읽으세요.md`의 Salesforce 로그인 절에 한 줄 추가:

> 앱을 연 뒤 **설정** 탭의 「로그인」버튼으로도 같은 브라우저 로그인을 할 수 있습니다.

PowerShell 명령 안내는 유지(백업 경로).

- [ ] **Step 2: Update `docs/local-app.md`**

SF 로그인 안내에 동일하게 설정 탭 「로그인」·목록·「이 계정 사용」·행 로그아웃을 짧게 언급.

- [ ] **Step 3: Commit** (사용자 요청 시에만)

```bash
git add 00-여기부터-읽으세요.md docs/local-app.md docs/superpowers/specs/2026-08-13-sf-login-logout-design.md docs/superpowers/plans/2026-08-13-sf-login-logout.md
git commit -m "docs: SF settings login/logout plan and user guide"
```

---

## Spec coverage (self-review)

| Spec 요구 | Task |
|-----------|------|
| 목록 (`sf org list`) | Task 1 + 3 |
| 로그인 버튼 (`sf org login web`) | Task 2 + 3 |
| 행 로그아웃 | Task 1 + 3 |
| 「이 계정 사용」→ yaml | Task 3 |
| 새로고침 | Task 3 |
| 토큰 UI 비저장 | Global + Task 3 caption |
| 단위 테스트 mock | Task 1–2 |
| 문서 안내 | Task 4 |
| 현재 alias 전용 로그아웃 버튼 없음 | Task 3 (행만) |

Placeholder scan: none intentional.  
Type consistency: `SfOrgRow`, `list_sf_orgs` → `list[SfOrgRow]`, `login_sf_org` / `logout_sf_org` → `None` or raise `SfCliStatusError`.
