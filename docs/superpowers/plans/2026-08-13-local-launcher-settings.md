# Local Launcher + Settings UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 바탕화면 아이콘으로 로컬 Streamlit(`127.0.0.1:8501`)을 띄우고, 「설정」탭에서 PMS 키·경로 등을 UI로 저장한다.

**Architecture:** 시크릿/설정 쓰기는 `config_store` 헬퍼로 분리한다. Streamlit 「설정」탭이 이 헬퍼와 SF CLI 상태 조회를 호출한다. `launch-local-app.ps1`은 localhost 전용 기동·브라우저 오픈만 담당하고, 기존 hub(Tailscale) 스크립트는 건드리지 않는다.

**Tech Stack:** Python 3.11+, Streamlit, PyYAML, python-dotenv, PowerShell, pytest

**Spec:** `docs/superpowers/specs/2026-08-13-local-launcher-settings-design.md`

## Global Constraints

- 대상: 본인(Ethan) 전용; 팀 설치 마법사·exe·네이티브 런처 창 금지
- 로컬 런처 바인딩: `127.0.0.1` / port `8501` only
- SF 토큰은 UI에 받지 않음 — `sf CLI` + `sf_org_alias`만
- `.env`의 `PMS_API_KEY`만 시크릿 UI 저장; `SF_INSTANCE_URL`/`SF_ACCESS_TOKEN` 유도 금지
- 기존 `scripts/start-hub-streamlit.ps1`, `scripts/register-hub-autostart.ps1` 유지·역할 분리
- 서버 중지 UI는 1차 범위 밖
- Windows; 경로 short path 패턴은 hub 스크립트와 동일하게 재사용 가능
- TDD: 헬퍼는 테스트 먼저; 커밋은 사용자 요청 시에만 (플랜 Step의 commit은 사용자가 요청하기 전까지 건너뜀)

## File map

| File | Responsibility |
|------|----------------|
| `src/ai_work_automation/config_store.py` | `.env` 키 upsert, `settings.yaml` 부분 갱신, env 반영 |
| `src/ai_work_automation/sf/cli_status.py` | `sf org display`로 연결 상태 조회 (UI용) |
| `tests/test_config_store.py` | env/yaml 저장 단위 테스트 |
| `tests/test_sf_cli_status.py` | CLI 상태 파싱 단위 테스트 |
| `src/ai_work_automation/webui.py` | 「설정」탭 UI |
| `scripts/launch-local-app.ps1` | 로컬 기동 + 브라우저 |
| `scripts/register-local-app-shortcut.ps1` | 바탕화면 바로가기 |
| `docs/local-app.md` | 사용 안내 한 페이지 |
| `README.md` | 로컬 앱 링크 한 절 |

---

### Task 1: `config_store` — `.env` upsert

**Files:**
- Create: `src/ai_work_automation/config_store.py`
- Test: `tests/test_config_store.py`

**Interfaces:**
- Produces:
  - `upsert_env_key(env_path: Path, key: str, value: str) -> None`
  - `env_key_is_set(env_path: Path, key: str) -> bool`
  - `apply_env_key_to_process(key: str, value: str) -> None`  # sets `os.environ[key]`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config_store.py
from pathlib import Path
import os

from ai_work_automation.config_store import (
    upsert_env_key,
    env_key_is_set,
    apply_env_key_to_process,
)


def test_upsert_env_key_adds_new_key(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("FOO=1\n", encoding="utf-8")
    upsert_env_key(env, "PMS_API_KEY", "secret-abc")
    text = env.read_text(encoding="utf-8")
    assert "FOO=1" in text
    assert "PMS_API_KEY=secret-abc" in text


def test_upsert_env_key_replaces_existing(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("PMS_API_KEY=old\nBAR=2\n", encoding="utf-8")
    upsert_env_key(env, "PMS_API_KEY", "new")
    lines = env.read_text(encoding="utf-8").splitlines()
    assert lines.count("PMS_API_KEY=new") == 1
    assert "PMS_API_KEY=old" not in lines
    assert "BAR=2" in lines


def test_upsert_env_key_creates_file(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    upsert_env_key(env, "PMS_API_KEY", "x")
    assert env.read_text(encoding="utf-8").strip() == "PMS_API_KEY=x"


def test_env_key_is_set(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("PMS_API_KEY=\n", encoding="utf-8")
    assert env_key_is_set(env, "PMS_API_KEY") is False
    env.write_text("PMS_API_KEY=abc\n", encoding="utf-8")
    assert env_key_is_set(env, "PMS_API_KEY") is True
    assert env_key_is_set(env, "MISSING") is False


def test_apply_env_key_to_process() -> None:
    apply_env_key_to_process("PMS_API_KEY", "runtime-val")
    assert os.environ["PMS_API_KEY"] == "runtime-val"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_config_store.py -v`  
Expected: FAIL (`ModuleNotFoundError` or import error for `config_store`)

- [ ] **Step 3: Minimal implementation**

```python
# src/ai_work_automation/config_store.py
from __future__ import annotations

import os
import re
from pathlib import Path

_ENV_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def upsert_env_key(env_path: Path, key: str, value: str) -> None:
    lines: list[str] = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    found = False
    for line in lines:
        m = _ENV_LINE.match(line)
        if m and m.group(1) == key:
            out.append(f"{key}={value}")
            found = True
        else:
            out.append(line)
    if not found:
        out.append(f"{key}={value}")
    env_path.write_text("\n".join(out) + "\n", encoding="utf-8")


def env_key_is_set(env_path: Path, key: str) -> bool:
    if not env_path.exists():
        return False
    for line in env_path.read_text(encoding="utf-8").splitlines():
        m = _ENV_LINE.match(line)
        if m and m.group(1) == key:
            return bool(m.group(2).strip())
    return False


def apply_env_key_to_process(key: str, value: str) -> None:
    os.environ[key] = value
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_config_store.py -v`  
Expected: PASS

- [ ] **Step 5: Commit** (사용자 요청 시에만)

```bash
git add src/ai_work_automation/config_store.py tests/test_config_store.py
git commit -m "feat: add .env upsert helpers for settings UI"
```

---

### Task 2: `config_store` — `settings.yaml` 부분 갱신

**Files:**
- Modify: `src/ai_work_automation/config_store.py`
- Modify: `tests/test_config_store.py`

**Interfaces:**
- Consumes: Task 1 module
- Produces:
  - `update_settings_yaml(path: Path, updates: dict[str, object]) -> None`  
    Top-level keys only. Values: `str | bool | int | float | None`.  
    `None` → YAML `null` (예: 경로 비우기). Path-like는 `str`로 저장.

- [ ] **Step 1: Write failing tests**

```python
# append to tests/test_config_store.py
import yaml
from ai_work_automation.config_store import update_settings_yaml
from ai_work_automation.settings import load_settings


def test_update_settings_yaml_preserves_other_keys(tmp_path: Path) -> None:
    path = tmp_path / "settings.yaml"
    path.write_text(
        'automation_enabled_after: "2026-12-01T00:00:00+09:00"\n'
        "dry_run: true\n"
        "pms_project_id: 1\n",
        encoding="utf-8",
    )
    update_settings_yaml(path, {"dry_run": False, "sf_org_alias": "parksystems"})
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert raw["dry_run"] is False
    assert raw["sf_org_alias"] == "parksystems"
    assert raw["pms_project_id"] == 1
    s = load_settings(path)
    assert s.dry_run is False
    assert s.sf_org_alias == "parksystems"


def test_update_settings_yaml_field_report_root(tmp_path: Path) -> None:
    path = tmp_path / "settings.yaml"
    path.write_text(
        'automation_enabled_after: "2026-12-01T00:00:00+09:00"\n',
        encoding="utf-8",
    )
    root = str(tmp_path / "DFS2")
    update_settings_yaml(path, {"field_report_root": root})
    s = load_settings(path)
    assert s.field_report_root == Path(root)
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_config_store.py::test_update_settings_yaml_preserves_other_keys -v`  
Expected: FAIL (`update_settings_yaml` missing)

- [ ] **Step 3: Implement**

```python
# add to config_store.py
import yaml


def update_settings_yaml(path: Path, updates: dict[str, object]) -> None:
    raw: dict = {}
    if path.exists():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"settings root must be a mapping: {path}")
        raw = loaded
    for key, value in updates.items():
        if isinstance(value, Path):
            raw[key] = str(value)
        else:
            raw[key] = value
    path.write_text(
        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
```

Note: PyYAML dump may drop comments in the working `settings.yaml`. Acceptable per spec (working file, not `settings.example.yaml`).

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_config_store.py -v`  
Expected: all PASS

- [ ] **Step 5: Commit** (사용자 요청 시에만)

---

### Task 3: SF CLI 상태 헬퍼

**Files:**
- Create: `src/ai_work_automation/sf/cli_status.py`
- Test: `tests/test_sf_cli_status.py`

**Interfaces:**
- Produces:
  - `@dataclass class SfCliStatus: ok: bool; connected: bool; username: str | None; alias: str; message: str`
  - `get_sf_cli_status(org_alias: str, run_sf_command: Callable[[list[str]], dict] | None = None) -> SfCliStatus`  
    Default runner: same subprocess style as `token_provider._run_sf_json_subprocess` but only `org display` (no access token).  
    Prefer injecting `run_sf_command` in tests.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_sf_cli_status.py
from ai_work_automation.sf.cli_status import get_sf_cli_status


def test_get_sf_cli_status_connected() -> None:
    def fake(args: list[str]) -> dict:
        assert args[:2] == ["org", "display"]
        return {
            "status": 0,
            "result": {
                "connectedStatus": "Connected",
                "username": "ethan.lee@parksystems.com",
            },
        }

    st = get_sf_cli_status("parksystems", run_sf_command=fake)
    assert st.ok is True
    assert st.connected is True
    assert st.username == "ethan.lee@parksystems.com"
    assert st.alias == "parksystems"


def test_get_sf_cli_status_not_connected() -> None:
    def fake(_args: list[str]) -> dict:
        return {"status": 0, "result": {"connectedStatus": "Disconnected"}}

    st = get_sf_cli_status("parksystems", run_sf_command=fake)
    assert st.connected is False
    assert st.ok is True


def test_get_sf_cli_status_cli_error() -> None:
    def fake(_args: list[str]) -> dict:
        return {"status": 1, "message": "no org"}

    st = get_sf_cli_status("x", run_sf_command=fake)
    assert st.ok is False
    assert "no org" in st.message
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_sf_cli_status.py -v`  
Expected: FAIL (module missing)

- [ ] **Step 3: Implement**

```python
# src/ai_work_automation/sf/cli_status.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ai_work_automation.sf.token_provider import _run_sf_json_subprocess, SfCredentialError


@dataclass(frozen=True)
class SfCliStatus:
    ok: bool
    connected: bool
    username: str | None
    alias: str
    message: str


def get_sf_cli_status(
    org_alias: str,
    run_sf_command: Callable[[list[str]], dict[str, Any]] | None = None,
) -> SfCliStatus:
    runner = run_sf_command or _run_sf_json_subprocess
    try:
        data = runner(["org", "display", "--target-org", org_alias])
    except SfCredentialError as exc:
        return SfCliStatus(
            ok=False, connected=False, username=None, alias=org_alias, message=str(exc)
        )
    if data.get("status") != 0:
        msg = str(data.get("message") or data)[:200]
        return SfCliStatus(
            ok=False, connected=False, username=None, alias=org_alias, message=msg
        )
    result = data.get("result") or {}
    status = str(result.get("connectedStatus") or "")
    connected = status.lower() == "connected"
    return SfCliStatus(
        ok=True,
        connected=connected,
        username=result.get("username"),
        alias=org_alias,
        message=status or ("Connected" if connected else "Not connected"),
    )
```

If importing `_run_sf_json_subprocess` is undesirable (private), extract a shared `run_sf_json` in `token_provider` and use it from both — prefer smallest change: import private with comment, or duplicate thin subprocess helper in `cli_status.py` matching `token_provider` (duplicate ~15 lines OK to avoid refactor churn).

**Prefer:** duplicate the small subprocess helper inside `cli_status.py` (copy from `token_provider._run_sf_json_subprocess`) to avoid exporting privates. Tests inject `run_sf_command` so default path is untested or lightly smoke-tested.

- [ ] **Step 4: Run — expect PASS**

Run: `pytest tests/test_sf_cli_status.py tests/test_token_provider.py -v`  
Expected: PASS

- [ ] **Step 5: Commit** (사용자 요청 시에만)

---

### Task 4: Streamlit 「설정」탭

**Files:**
- Modify: `src/ai_work_automation/webui.py` (tabs list ~1328, add `tab_settings` and render function)

**Interfaces:**
- Consumes: `upsert_env_key`, `env_key_is_set`, `apply_env_key_to_process`, `update_settings_yaml`, `get_sf_cli_status`, `SETTINGS_PATH`, `load_settings`
- Produces: UI only; `.env` path = repo-root `.env` → `Path(".env")` (cwd = repo when launched)

- [ ] **Step 1: Add render helper and fifth tab**

Near other `_render_*` helpers, add:

```python
def _render_settings_tab() -> None:
    from ai_work_automation.config_store import (
        apply_env_key_to_process,
        env_key_is_set,
        update_settings_yaml,
        upsert_env_key,
    )
    from ai_work_automation.sf.cli_status import get_sf_cli_status

    env_path = Path(".env")
    s = _settings()

    st.subheader("시크릿")
    pms_set = env_key_is_set(env_path, "PMS_API_KEY")
    st.caption("PMS API Key: " + ("저장됨" if pms_set else "미설정"))
    new_key = st.text_input("PMS API Key", type="password", value="", key="settings_pms_key")
    if st.button("PMS 키 저장", key="settings_save_pms"):
        if not new_key.strip():
            st.error("키를 입력하세요.")
        else:
            upsert_env_key(env_path, "PMS_API_KEY", new_key.strip())
            apply_env_key_to_process("PMS_API_KEY", new_key.strip())
            st.success("PMS API Key를 .env에 저장했습니다.")

    st.subheader("일반")
    root_val = str(s.field_report_root) if s.field_report_root else ""
    field_root = st.text_input("field_report_root (DFS2 경로)", value=root_val)
    dry_run = st.toggle("dry_run", value=s.dry_run)
    org_alias = st.text_input("sf_org_alias", value=s.sf_org_alias)
    if field_root.strip():
        exists = Path(field_root.strip()).exists()
        st.caption("경로: " + ("존재함" if exists else "없음(동기화/경로 확인)"))
    if st.button("설정 저장", key="settings_save_yaml"):
        update_settings_yaml(
            SETTINGS_PATH,
            {
                "field_report_root": field_root.strip() or None,
                "dry_run": dry_run,
                "sf_org_alias": org_alias.strip() or "parksystems",
            },
        )
        st.success("config/settings.yaml 저장됨. 다음 동작부터 반영됩니다.")
        st.rerun()

    st.subheader("Salesforce CLI")
    status = get_sf_cli_status(org_alias.strip() or s.sf_org_alias)
    if status.ok and status.connected:
        st.success(f"Connected — {status.username or ''} ({status.alias})")
    elif status.ok:
        st.warning(status.message)
    else:
        st.error(status.message)
    st.code(f"sf org login web --alias {org_alias.strip() or s.sf_org_alias}", language="powershell")
    st.caption("SF 액세스 토큰은 UI에 저장하지 않습니다. CLI 로그인을 사용하세요.")
```

Change tabs:

```python
tab_scan, tab_search, tab_field, tab_status, tab_settings = st.tabs(
    ["VOC→PMS", "케이스 검색", "출장 보고", "이슈 상태", "설정"]
)
```

And:

```python
with tab_settings:
    _render_settings_tab()
```

Ensure `_settings()` still reads fresh file after yaml save (`st.rerun()` handles it). No settings cache beyond process — `load_settings` each call is fine.

- [ ] **Step 2: Manual smoke (or skip if headless)**

Run:  
`.\.venv\Scripts\python.exe -m streamlit run src\ai_work_automation\webui.py --server.headless true`  
Open 설정 탭 — 위젯 렌더 확인.  
Optional: `pytest tests/test_config_store.py tests/test_sf_cli_status.py -v` still PASS.

- [ ] **Step 3: Commit** (사용자 요청 시에만)

---

### Task 5: `launch-local-app.ps1`

**Files:**
- Create: `scripts/launch-local-app.ps1`

**Interfaces:**
- Consumes: `.venv\Scripts\python.exe`, `src\ai_work_automation\webui.py`
- Produces: Listen on `127.0.0.1:8501`, open browser, log `logs/local-app.log`

- [ ] **Step 1: Write script**

Base on `scripts/start-hub-streamlit.ps1` but:

- Default `$Address = "127.0.0.1"`, `$Port = 8501`, `$DelaySeconds = 0`
- If port already Listen → do **not** kill; skip Start-Process
- Always attempt browser: `Start-Process "http://127.0.0.1:$Port"`
- Log file: `logs/local-app.log`
- Do **not** bind `0.0.0.0`

Outline:

```powershell
#Requires -Version 5.1
param(
    [int]$DelaySeconds = 0,
    [int]$Port = 8501,
    [string]$Address = "127.0.0.1"
)
# Get-ShortPath + venv/webui checks (same as hub)
# If Listen on $Port: Write-Log "already running"; Start-Process "http://127.0.0.1:$Port"; exit 0
# Else: Start-Process python -m streamlit run ... --server.address=$Address ...
# Wait for Listen (loop up to ~15s), then Start-Process browser URL
```

- [ ] **Step 2: Manual test**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\launch-local-app.ps1
```

Expected: browser opens; `Get-NetTCPConnection -LocalPort 8501` shows Listen on 127.0.0.1.  
Run script again: no second python storm; browser reopens.

- [ ] **Step 3: Commit** (사용자 요청 시에만)

---

### Task 6: 바로가기 등록 + 문서

**Files:**
- Create: `scripts/register-local-app-shortcut.ps1`
- Create: `docs/local-app.md`
- Modify: `README.md` (웹 UI 절 아래에 로컬 앱 링크)

- [ ] **Step 1: Shortcut script**

```powershell
#Requires -Version 5.1
param(
    [switch]$StartMenu
)
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Launch = (Resolve-Path (Join-Path $PSScriptRoot "launch-local-app.ps1")).Path
$Desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $Desktop "AI 업무자동화.lnk"
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath = "powershell.exe"
$lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Launch`""
$lnk.WorkingDirectory = $RepoRoot
$lnk.WindowStyle = 7  # minimized
$lnk.Description = "AI 업무자동화 (local Streamlit)"
$lnk.Save()
Write-Host "Created: $lnkPath"
# if -StartMenu: also create under [Environment]::GetFolderPath("StartMenu")\Programs
```

- [ ] **Step 2: Docs**

`docs/local-app.md`:

- 1회: `pip install -e ".[ui]"`, `sf org login`, copy `.env`/`settings.yaml`
- 바로가기: `register-local-app-shortcut.ps1`
- 아이콘 클릭 → localhost:8501
- 설정 탭에서 PMS 키·경로
- hub(`0.0.0.0`)와 동시 사용 금지(같은 포트)
- 링크 to hub-autostart for Tailscale hub

README: short bullet pointing to `docs/local-app.md`.

- [ ] **Step 3: Manual** — run register script, click shortcut once.

- [ ] **Step 4: Commit** (사용자 요청 시에만)

---

### Task 7: 회귀 확인

- [ ] **Step 1: Run unit suite**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_config_store.py tests/test_sf_cli_status.py tests/test_token_provider.py tests/test_settings.py -v
```

Expected: PASS

- [ ] **Step 2: Quick webui import check**

```powershell
.\.venv\Scripts\python.exe -c "import ai_work_automation.webui"
```

Expected: exit 0 (may run streamlit side effects — if so, instead compile):

```powershell
.\.venv\Scripts\python.exe -m py_compile src\ai_work_automation\webui.py src\ai_work_automation\config_store.py src\ai_work_automation\sf\cli_status.py
```

- [ ] **Step 3: Spec checklist**

Confirm against spec §1 success criteria 1–4 and §2 non-goals (no exe, no 0.0.0.0 in local launcher).

---

## Spec coverage (self-review)

| Spec item | Task |
|-----------|------|
| Icon → localhost:8501 | 5, 6 |
| Reuse if already listening | 5 |
| Settings tab PMS / root / dry_run / alias | 4 |
| `.env` / yaml storage | 1, 2 |
| SF CLI status, no token fields | 3, 4 |
| Hub scripts untouched | 5 (new files only) |
| No server-stop UI | 4 (omitted) |
| Docs | 6 |
| Unit tests helpers | 1–3, 7 |

## Placeholder / consistency check

- Function names aligned: `upsert_env_key`, `update_settings_yaml`, `get_sf_cli_status`
- Port/address literals: `127.0.0.1` / `8501`
- Commit steps deferred to user request (Global Constraints)
