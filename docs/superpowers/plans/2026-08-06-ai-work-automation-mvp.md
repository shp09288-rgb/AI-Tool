# AI 업무 자동화 MVP (P0+P1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사용자가 배포 이후 Case만 선택해 실행하면, VOC+SW Work Order에 대해 Human Gate 승인 후 PMS 이슈를 만들고 Salesforce Activities에 URL을 회수하는 CLI MVP를 만든다.

**Architecture:** 로컬 Python 패키지 + YAML 라우팅. 옵트인·컷오프·작업 로그는 로컬 JSON. Salesforce/PMS는 httpx 기반 어댑터(테스트는 mock). 파이프라인: 선택 확인 → 컷오프 → SF 읽기 → 라우터 → 초안(템플릿, AI는 후속) → Human Gate → PMS → Activities 이어쓰기.

**Tech Stack:** Python 3.11+, pytest, pydantic v2, httpx, PyYAML, Typer, rich(선택). 패키지 레이아웃 `src/ai_work_automation/`.

## Global Constraints

- 문서·커밋 메시지·사용자 대면 문구는 **한국어** (코드 식별자는 영어 허용).
- 배포 컷오프 이전 Case/WO에 **쓰기 API 호출 0건**.
- **옵트인되지 않은** Case는 파이프라인에 넣지 않음 (skip 로그만).
- Outlook 자동 발송·Workful·Teams·릴리즈 노트는 **이 계획 범위 밖** (후속 계획).
- Activities는 **이어 붙이기만** (기존 텍스트 삭제 금지).
- 외부 생성 전 Human Gate **기본 ON**.
- TDD: 실패 테스트 → 최소 구현 → 통과 → 커밋.
- 시크릿(`.env`, 토큰)은 커밋하지 않음.

---

## 범위 안내

이 계획은 스펙 우선순위 **P0 + P1**만 다룬다. 완료 시 동작하는 소프트웨어:

1. Case 옵트인 선택/해제  
2. 컷오프 가드  
3. Salesforce Case/WO 읽기 + Activities 이어쓰기 (실연동 또는 mock)  
4. VOC+SW → `pms` 라우팅  
5. CLI Human Gate  
6. PMS 이슈 생성 + URL 회수  

**후속 계획(별도):** Outlook Technical Support 초안, Workful, Teams, 릴리즈 노트, Draft AI(LLM), CDC 트리거.

---

## 파일 구조 (생성 예정)

```text
pyproject.toml
.gitignore
.env.example
config/
  settings.example.yaml
  routes.yaml
src/ai_work_automation/
  __init__.py
  models.py              # CaseRecord, WorkOrderRecord, DraftContent, ConnectorResult
  settings.py            # YAML+환경변수 로드
  cutoff.py              # is_after_cutoff
  opt_in.py              # OptInStore (JSON)
  job_log.py             # JobLogStore
  router.py              # resolve_targets
  draft_template.py      # PMS용 제목/본문 템플릿 (LLM 없음)
  gate/human.py          # approve_or_reject (CLI)
  connectors/base.py     # Protocol + ConnectorResult
  connectors/pms.py      # PmsConnector
  sf/client.py           # SalesforceHttpClient (OAuth + REST)
  sf/adapter.py          # 읽기/Activities append + 안전 가드
  pipeline.py            # run_case_automation
  cli.py                 # Typer 진입점
tests/
  test_cutoff.py
  test_opt_in.py
  test_router.py
  test_draft_template.py
  test_human_gate.py
  test_pms_connector.py
  test_sf_adapter_safety.py
  test_pipeline.py
  conftest.py
```

---

### Task 1: 프로젝트 골격 + 도메인 모델

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/ai_work_automation/__init__.py`
- Create: `src/ai_work_automation/models.py`
- Create: `tests/test_models.py`
- Create: `tests/conftest.py`

**Interfaces:**
- Consumes: 없음
- Produces: `CaseRecord`, `WorkOrderRecord`, `DraftContent`, `ConnectorResult` (pydantic)

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_models.py
from datetime import datetime, timezone
from ai_work_automation.models import CaseRecord, WorkOrderRecord, ConnectorResult


def test_case_record_requires_id_and_created_date():
    c = CaseRecord(
        id="500XX000001",
        case_number="00196720",
        subject="테스트",
        created_date=datetime(2026, 12, 2, tzinfo=timezone.utc),
    )
    assert c.id == "500XX000001"


def test_connector_result_ok_has_url():
    r = ConnectorResult(ok=True, ref="4710", url="https://pms.example/issues/4710")
    assert r.ok is True
    assert r.url.endswith("4710")
```

- [ ] **Step 2: 테스트 실행해 실패 확인**

Run: `pytest tests/test_models.py -v`  
Expected: FAIL (`ModuleNotFoundError` 또는 import 오류)

- [ ] **Step 3: 최소 구현**

`pyproject.toml`:

```toml
[project]
name = "ai-work-automation"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.6",
  "httpx>=0.27",
  "PyYAML>=6.0",
  "typer>=0.12",
  "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-mock>=3.12"]

[project.scripts]
ai-work = "ai_work_automation.cli:app"

[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

`.gitignore`:

```gitignore
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
data/
*.egg-info/
dist/
build/
```

`src/ai_work_automation/models.py`:

```python
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class CaseRecord(BaseModel):
    id: str
    case_number: str
    subject: str
    created_date: datetime
    description: str | None = None
    status: str | None = None


class WorkOrderRecord(BaseModel):
    id: str
    work_order_number: str
    record_type: str
    relevant_department: str | None = None
    subject: str | None = None
    activities: str | None = None
    case_id: str | None = None
    created_date: datetime | None = None
    priority: str | None = None
    sw_version: str | None = None


class DraftContent(BaseModel):
    title: str
    body: str
    extra: dict[str, Any] = Field(default_factory=dict)


class ConnectorResult(BaseModel):
    ok: bool
    ref: str | None = None
    url: str | None = None
    error: str | None = None
    retryable: bool = False
    raw: dict[str, Any] | None = None
```

`src/ai_work_automation/__init__.py`:

```python
__version__ = "0.1.0"
```

`tests/conftest.py`:

```python
from datetime import datetime, timezone

import pytest

from ai_work_automation.models import CaseRecord, WorkOrderRecord


@pytest.fixture
def sample_case() -> CaseRecord:
    return CaseRecord(
        id="500CASE1",
        case_number="00190001",
        subject="AST / NX / Servo OFF",
        created_date=datetime(2026, 12, 2, 1, 0, tzinfo=timezone.utc),
        description="상세 설명",
    )


@pytest.fixture
def sample_wo_voc_sw(sample_case: CaseRecord) -> WorkOrderRecord:
    return WorkOrderRecord(
        id="0WORK1",
        work_order_number="00025947",
        record_type="VOC",
        relevant_department="SW",
        subject=sample_case.subject,
        activities="",
        case_id=sample_case.id,
        created_date=sample_case.created_date,
        priority="High",
    )
```

- [ ] **Step 4: 테스트 통과 확인**

Run: `python -m venv .venv` → Windows: `.venv\Scripts\activate` → `pip install -e ".[dev]"` → `pytest tests/test_models.py -v`  
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add pyproject.toml .gitignore src/ai_work_automation tests/test_models.py tests/conftest.py
git commit -m "feat: 프로젝트 골격과 도메인 모델 추가"
```

---

### Task 2: 컷오프 가드

**Files:**
- Create: `src/ai_work_automation/cutoff.py`
- Create: `tests/test_cutoff.py`

**Interfaces:**
- Consumes: `CaseRecord.created_date`
- Produces: `is_after_cutoff(created: datetime, cutoff: datetime) -> bool`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_cutoff.py
from datetime import datetime, timezone

from ai_work_automation.cutoff import is_after_cutoff


def test_before_cutoff_is_blocked():
    created = datetime(2024, 7, 7, tzinfo=timezone.utc)
    cutoff = datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert is_after_cutoff(created, cutoff) is False


def test_on_or_after_cutoff_is_allowed():
    created = datetime(2026, 12, 1, tzinfo=timezone.utc)
    cutoff = datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert is_after_cutoff(created, cutoff) is True
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_cutoff.py -v`  
Expected: FAIL (import 오류)

- [ ] **Step 3: 구현**

```python
# src/ai_work_automation/cutoff.py
from datetime import datetime


def is_after_cutoff(created: datetime, cutoff: datetime) -> bool:
    if created.tzinfo is None or cutoff.tzinfo is None:
        raise ValueError("created와 cutoff는 timezone-aware datetime이어야 합니다")
    return created >= cutoff
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_cutoff.py -v`  
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/ai_work_automation/cutoff.py tests/test_cutoff.py
git commit -m "feat: 배포 컷오프 가드 추가"
```

---

### Task 3: 옵트인 저장소

**Files:**
- Create: `src/ai_work_automation/opt_in.py`
- Create: `tests/test_opt_in.py`

**Interfaces:**
- Consumes: 파일 경로
- Produces: `OptInStore.is_selected(case_id) -> bool`, `select`, `deselect`, `list_selected`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_opt_in.py
from pathlib import Path

from ai_work_automation.opt_in import OptInStore


def test_select_and_check(tmp_path: Path):
    store = OptInStore(tmp_path / "opt_in.json")
    assert store.is_selected("500A") is False
    store.select("500A")
    assert store.is_selected("500A") is True
    assert "500A" in store.list_selected()


def test_deselect(tmp_path: Path):
    store = OptInStore(tmp_path / "opt_in.json")
    store.select("500A")
    store.deselect("500A")
    assert store.is_selected("500A") is False
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_opt_in.py -v`  
Expected: FAIL

- [ ] **Step 3: 구현**

```python
# src/ai_work_automation/opt_in.py
import json
from pathlib import Path


class OptInStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write([])

    def _read(self) -> list[str]:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, ids: list[str]) -> None:
        self.path.write_text(
            json.dumps(sorted(set(ids)), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def is_selected(self, case_id: str) -> bool:
        return case_id in self._read()

    def select(self, case_id: str) -> None:
        ids = self._read()
        ids.append(case_id)
        self._write(ids)

    def deselect(self, case_id: str) -> None:
        self._write([i for i in self._read() if i != case_id])

    def list_selected(self) -> list[str]:
        return self._read()
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_opt_in.py -v`  
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/ai_work_automation/opt_in.py tests/test_opt_in.py
git commit -m "feat: Case 옵트인 JSON 저장소 추가"
```

---

### Task 4: 설정 로드 + 라우터

**Files:**
- Create: `src/ai_work_automation/settings.py`
- Create: `src/ai_work_automation/router.py`
- Create: `config/routes.yaml`
- Create: `config/settings.example.yaml`
- Create: `tests/test_router.py`

**Interfaces:**
- Consumes: `WorkOrderRecord.record_type`, `relevant_department`
- Produces: `resolve_targets(wo, routes) -> list[str]`, `load_routes(path) -> list[RouteRule]`, `Settings`

- [ ] **Step 1: 실패 테스트 작성**

```python
# tests/test_router.py
from pathlib import Path

from ai_work_automation.models import WorkOrderRecord
from ai_work_automation.router import load_routes, resolve_targets
from datetime import datetime, timezone


def test_voc_sw_routes_to_pms(tmp_path: Path):
    routes_file = tmp_path / "routes.yaml"
    routes_file.write_text(
        """
routes:
  - id: voc-sw-pms
    when:
      recordType: VOC
      department: SW
    targets: [pms]
""",
        encoding="utf-8",
    )
    routes = load_routes(routes_file)
    wo = WorkOrderRecord(
        id="1",
        work_order_number="1",
        record_type="VOC",
        relevant_department="SW",
        created_date=datetime(2026, 12, 2, tzinfo=timezone.utc),
    )
    assert resolve_targets(wo, routes) == ["pms"]


def test_unmatched_returns_empty(tmp_path: Path):
    routes_file = tmp_path / "routes.yaml"
    routes_file.write_text(
        "routes:\n  - id: x\n    when: {recordType: VOC, department: SW}\n    targets: [pms]\n",
        encoding="utf-8",
    )
    routes = load_routes(routes_file)
    wo = WorkOrderRecord(
        id="1",
        work_order_number="1",
        record_type="VOC",
        relevant_department="HW",
        created_date=datetime(2026, 12, 2, tzinfo=timezone.utc),
    )
    assert resolve_targets(wo, routes) == []
```

- [ ] **Step 2: 실패 확인**

Run: `pytest tests/test_router.py -v`  
Expected: FAIL

- [ ] **Step 3: 구현**

```python
# src/ai_work_automation/router.py
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from ai_work_automation.models import WorkOrderRecord


class RouteWhen(BaseModel):
    recordType: str
    department: str | None = None


class RouteRule(BaseModel):
    id: str
    when: RouteWhen
    targets: list[str]
    require_human_gate: bool = True


class RoutesFile(BaseModel):
    routes: list[RouteRule] = Field(default_factory=list)


def load_routes(path: Path) -> list[RouteRule]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return RoutesFile.model_validate(data).routes


def resolve_targets(wo: WorkOrderRecord, routes: list[RouteRule]) -> list[str]:
    matched: list[str] = []
    for rule in routes:
        if rule.when.recordType != wo.record_type:
            continue
        if rule.when.department is not None:
            if (wo.relevant_department or "") != rule.when.department:
                continue
        matched.extend(rule.targets)
    # 순서 유지 중복 제거
    seen: set[str] = set()
    out: list[str] = []
    for t in matched:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out
```

```python
# src/ai_work_automation/settings.py
from datetime import datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class Settings(BaseModel):
    automation_enabled_after: datetime
    opt_in_path: Path = Path("data/opt_in.json")
    job_log_path: Path = Path("data/job_log.jsonl")
    routes_path: Path = Path("config/routes.yaml")
    pms_base_url: str = "https://pms.parksystems.com"
    pms_api_key_env: str = "PMS_API_KEY"
    sf_instance_url_env: str = "SF_INSTANCE_URL"
    sf_access_token_env: str = "SF_ACCESS_TOKEN"
    dry_run: bool = False


def load_settings(path: Path) -> Settings:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return Settings.model_validate(raw)
```

`config/routes.yaml`:

```yaml
routes:
  - id: voc-sw-pms
    when:
      recordType: VOC
      department: SW
    targets: [pms]
    require_human_gate: true
```

`config/settings.example.yaml`:

```yaml
automation_enabled_after: "2026-12-01T00:00:00+09:00"
opt_in_path: data/opt_in.json
job_log_path: data/job_log.jsonl
routes_path: config/routes.yaml
pms_base_url: https://pms.parksystems.com
dry_run: true
```

- [ ] **Step 4: 통과 확인**

Run: `pytest tests/test_router.py -v`  
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
git add src/ai_work_automation/router.py src/ai_work_automation/settings.py config tests/test_router.py
git commit -m "feat: YAML 라우팅과 설정 로드 추가"
```

---

### Task 5: 작업 로그

**Files:**
- Create: `src/ai_work_automation/job_log.py`
- Create: `tests/test_job_log.py`

**Interfaces:**
- Produces: `JobLogStore.append(event: dict) -> None`, `read_all() -> list[dict]`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_job_log.py
from pathlib import Path

from ai_work_automation.job_log import JobLogStore


def test_append_and_read(tmp_path: Path):
    store = JobLogStore(tmp_path / "job.jsonl")
    store.append({"case_id": "500A", "status": "skipped", "reason": "not_selected"})
    rows = store.read_all()
    assert len(rows) == 1
    assert rows[0]["reason"] == "not_selected"
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_job_log.py -v`

- [ ] **Step 3: 구현**

```python
# src/ai_work_automation/job_log.py
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class JobLogStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("", encoding="utf-8")

    def append(self, event: dict[str, Any]) -> None:
        payload = {
            **event,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(line) for line in lines if line.strip()]
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_job_log.py -v`

- [ ] **Step 5: 커밋**

```bash
git add src/ai_work_automation/job_log.py tests/test_job_log.py
git commit -m "feat: JSONL 작업 로그 추가"
```

---

### Task 6: 초안 템플릿 + Human Gate

**Files:**
- Create: `src/ai_work_automation/draft_template.py`
- Create: `src/ai_work_automation/gate/__init__.py`
- Create: `src/ai_work_automation/gate/human.py`
- Create: `tests/test_draft_template.py`
- Create: `tests/test_human_gate.py`

**Interfaces:**
- Produces: `build_pms_draft(case, wo) -> DraftContent`
- Produces: `human_approve(draft, prompt_fn) -> bool`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_draft_template.py
from ai_work_automation.draft_template import build_pms_draft


def test_build_pms_draft_uses_case_subject(sample_case, sample_wo_voc_sw):
    draft = build_pms_draft(sample_case, sample_wo_voc_sw)
    assert draft.title == sample_case.subject
    assert "상세" in draft.body or (sample_case.description or "") in draft.body


# tests/test_human_gate.py
from ai_work_automation.gate.human import human_approve
from ai_work_automation.models import DraftContent


def test_approve_yes():
    draft = DraftContent(title="t", body="b")
    assert human_approve(draft, prompt_fn=lambda _: "y") is True


def test_reject_no():
    draft = DraftContent(title="t", body="b")
    assert human_approve(draft, prompt_fn=lambda _: "n") is False
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_draft_template.py tests/test_human_gate.py -v`

- [ ] **Step 3: 구현**

```python
# src/ai_work_automation/draft_template.py
from ai_work_automation.models import CaseRecord, DraftContent, WorkOrderRecord


def build_pms_draft(case: CaseRecord, wo: WorkOrderRecord) -> DraftContent:
    title = wo.subject or case.subject
    parts = [
        case.description or "",
        f"Work Order: {wo.work_order_number}",
        f"Priority: {wo.priority or ''}",
    ]
    if wo.sw_version:
        parts.append(f"SW ver.: {wo.sw_version}")
    body = "\n\n".join(p for p in parts if p)
    return DraftContent(title=title, body=body)
```

```python
# src/ai_work_automation/gate/__init__.py
```

```python
# src/ai_work_automation/gate/human.py
from collections.abc import Callable

from ai_work_automation.models import DraftContent


def human_approve(
    draft: DraftContent,
    prompt_fn: Callable[[str], str] | None = None,
) -> bool:
    ask = prompt_fn or input
    message = (
        f"제목: {draft.title}\n\n본문:\n{draft.body}\n\n"
        "이 내용으로 외부 게시를 승인할까요? [y/N]: "
    )
    answer = ask(message).strip().lower()
    return answer in {"y", "yes", "ㅇ"}
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_draft_template.py tests/test_human_gate.py -v`

- [ ] **Step 5: 커밋**

```bash
git add src/ai_work_automation/draft_template.py src/ai_work_automation/gate tests/test_draft_template.py tests/test_human_gate.py
git commit -m "feat: PMS 초안 템플릿과 CLI Human Gate 추가"
```

---

### Task 7: PMS 커넥터

**Files:**
- Create: `src/ai_work_automation/connectors/__init__.py`
- Create: `src/ai_work_automation/connectors/base.py`
- Create: `src/ai_work_automation/connectors/pms.py`
- Create: `tests/test_pms_connector.py`

**Interfaces:**
- Consumes: `DraftContent`, httpx 클라이언트
- Produces: `PmsConnector.create(draft) -> ConnectorResult`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_pms_connector.py
import httpx

from ai_work_automation.connectors.pms import PmsConnector
from ai_work_automation.models import DraftContent


def test_create_issue_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/issues.json")
        assert request.headers.get("X-Redmine-API-Key") == "secret"
        return httpx.Response(
            201,
            json={"issue": {"id": 4710}},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://pms.example")
    conn = PmsConnector(client=client, api_key="secret", base_url="https://pms.example")
    result = conn.create(DraftContent(title="제목", body="본문"), project_id=1)
    assert result.ok is True
    assert result.ref == "4710"
    assert result.url == "https://pms.example/issues/4710"


def test_create_issue_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="error")

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://pms.example")
    conn = PmsConnector(client=client, api_key="secret", base_url="https://pms.example")
    result = conn.create(DraftContent(title="t", body="b"), project_id=1)
    assert result.ok is False
    assert result.retryable is True
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_pms_connector.py -v`

- [ ] **Step 3: 구현**

```python
# src/ai_work_automation/connectors/base.py
from typing import Protocol

from ai_work_automation.models import ConnectorResult, DraftContent


class Connector(Protocol):
    def create(self, draft: DraftContent, **kwargs) -> ConnectorResult: ...
```

```python
# src/ai_work_automation/connectors/__init__.py
```

```python
# src/ai_work_automation/connectors/pms.py
from typing import Any

import httpx

from ai_work_automation.models import ConnectorResult, DraftContent


class PmsConnector:
    def __init__(self, client: httpx.Client, api_key: str, base_url: str) -> None:
        self.client = client
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def create(
        self,
        draft: DraftContent,
        *,
        project_id: int,
        tracker_id: int | None = None,
        priority_id: int | None = None,
    ) -> ConnectorResult:
        payload: dict[str, Any] = {
            "issue": {
                "project_id": project_id,
                "subject": draft.title,
                "description": draft.body,
            }
        }
        if tracker_id is not None:
            payload["issue"]["tracker_id"] = tracker_id
        if priority_id is not None:
            payload["issue"]["priority_id"] = priority_id
        try:
            resp = self.client.post(
                "/issues.json",
                json=payload,
                headers={"X-Redmine-API-Key": self.api_key},
            )
        except httpx.HTTPError as e:
            return ConnectorResult(ok=False, error=str(e), retryable=True)
        if resp.status_code >= 400:
            return ConnectorResult(
                ok=False,
                error=f"HTTP {resp.status_code}: {resp.text[:500]}",
                retryable=resp.status_code >= 500,
            )
        data = resp.json()
        issue_id = str(data["issue"]["id"])
        return ConnectorResult(
            ok=True,
            ref=issue_id,
            url=f"{self.base_url}/issues/{issue_id}",
            raw=data,
        )
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_pms_connector.py -v`

- [ ] **Step 5: 커밋**

```bash
git add src/ai_work_automation/connectors tests/test_pms_connector.py
git commit -m "feat: PMS(Redmine) 이슈 생성 커넥터 추가"
```

---

### Task 8: Salesforce 어댑터 (안전 가드 포함)

**Files:**
- Create: `src/ai_work_automation/sf/__init__.py`
- Create: `src/ai_work_automation/sf/client.py`
- Create: `src/ai_work_automation/sf/adapter.py`
- Create: `tests/test_sf_adapter_safety.py`

**Interfaces:**
- Consumes: cutoff, Case/WO id
- Produces: `SalesforceAdapter.get_case`, `get_work_orders_for_case`, `append_work_order_activities` (컷오프·선택 검사 후만 PATCH)

- [ ] **Step 1: 실패 테스트 (쓰기가 차단되는지)**

```python
# tests/test_sf_adapter_safety.py
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from ai_work_automation.models import WorkOrderRecord
from ai_work_automation.sf.adapter import SalesforceAdapter, SafetyError


def test_append_blocked_before_cutoff():
    client = MagicMock()
    adapter = SalesforceAdapter(
        client=client,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
    )
    wo = WorkOrderRecord(
        id="0WOOLD",
        work_order_number="1",
        record_type="VOC",
        activities="old",
        created_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    with pytest.raises(SafetyError):
        adapter.append_work_order_activities(
            wo,
            line="PMS – https://pms.example/issues/1",
            case_selected=True,
        )
    client.patch_sobject.assert_not_called()


def test_append_blocked_when_not_selected():
    client = MagicMock()
    adapter = SalesforceAdapter(
        client=client,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
    )
    wo = WorkOrderRecord(
        id="0WONEW",
        work_order_number="1",
        record_type="VOC",
        activities="",
        created_date=datetime(2026, 12, 2, tzinfo=timezone.utc),
    )
    with pytest.raises(SafetyError):
        adapter.append_work_order_activities(
            wo,
            line="PMS – https://pms.example/issues/1",
            case_selected=False,
        )
    client.patch_sobject.assert_not_called()


def test_append_succeeds_when_allowed():
    client = MagicMock()
    adapter = SalesforceAdapter(
        client=client,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        activities_field="VOC_Activities__c",
    )
    wo = WorkOrderRecord(
        id="0WONEW",
        work_order_number="1",
        record_type="VOC",
        activities="기존메모",
        created_date=datetime(2026, 12, 2, tzinfo=timezone.utc),
    )
    adapter.append_work_order_activities(
        wo,
        line="PMS – https://pms.example/issues/1",
        case_selected=True,
    )
    client.patch_sobject.assert_called_once()
    args, kwargs = client.patch_sobject.call_args
    assert args[0] == "WorkOrder"
    assert args[1] == "0WONEW"
    body = args[2]
    assert "기존메모" in body["VOC_Activities__c"]
    assert "PMS – https://pms.example/issues/1" in body["VOC_Activities__c"]
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_sf_adapter_safety.py -v`

- [ ] **Step 3: 구현**

```python
# src/ai_work_automation/sf/__init__.py
```

```python
# src/ai_work_automation/sf/client.py
from typing import Any

import httpx


class SalesforceHttpClient:
    """액세스 토큰은 외부에서 주입 (환경변수/수동). OAuth 교환은 후속."""

    def __init__(self, instance_url: str, access_token: str, api_version: str = "v59.0") -> None:
        self.instance_url = instance_url.rstrip("/")
        self.api_version = api_version
        self._client = httpx.Client(
            base_url=self.instance_url,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            timeout=60.0,
        )

    def get_sobject(self, object_name: str, record_id: str, fields: list[str] | None = None) -> dict[str, Any]:
        params = {}
        if fields:
            params["fields"] = ",".join(fields)
        r = self._client.get(f"/services/data/{self.api_version}/sobjects/{object_name}/{record_id}", params=params)
        r.raise_for_status()
        return r.json()

    def query(self, soql: str) -> dict[str, Any]:
        r = self._client.get(f"/services/data/{self.api_version}/query", params={"q": soql})
        r.raise_for_status()
        return r.json()

    def patch_sobject(self, object_name: str, record_id: str, body: dict[str, Any]) -> None:
        r = self._client.patch(
            f"/services/data/{self.api_version}/sobjects/{object_name}/{record_id}",
            json=body,
        )
        r.raise_for_status()
```

```python
# src/ai_work_automation/sf/adapter.py
from datetime import datetime
from typing import Any

from ai_work_automation.cutoff import is_after_cutoff
from ai_work_automation.models import CaseRecord, WorkOrderRecord
from ai_work_automation.sf.client import SalesforceHttpClient


class SafetyError(Exception):
    pass


class SalesforceAdapter:
    def __init__(
        self,
        client: SalesforceHttpClient | Any,
        cutoff: datetime,
        activities_field: str = "VOC_Activities__c",
        case_fields: list[str] | None = None,
        wo_fields: list[str] | None = None,
    ) -> None:
        self.client = client
        self.cutoff = cutoff
        self.activities_field = activities_field
        self.case_fields = case_fields or [
            "Id",
            "CaseNumber",
            "Subject",
            "Description",
            "CreatedDate",
            "Status",
        ]
        self.wo_fields = wo_fields or [
            "Id",
            "WorkOrderNumber",
            "Subject",
            "CreatedDate",
            "CaseId",
            "Priority",
            activities_field,
        ]

    def append_work_order_activities(
        self,
        wo: WorkOrderRecord,
        line: str,
        *,
        case_selected: bool,
    ) -> None:
        if not case_selected:
            raise SafetyError("옵트인되지 않은 Case의 Work Order는 수정할 수 없습니다")
        created = wo.created_date
        if created is None:
            raise SafetyError("Work Order CreatedDate가 없어 컷오프를 검사할 수 없습니다")
        if not is_after_cutoff(created, self.cutoff):
            raise SafetyError("컷오프 이전 Work Order는 수정할 수 없습니다")
        existing = wo.activities or ""
        separator = "\n" if existing and not existing.endswith("\n") else ""
        new_value = f"{existing}{separator}{line}"
        self.client.patch_sobject(
            "WorkOrder",
            wo.id,
            {self.activities_field: new_value},
        )

    def get_case(self, case_id: str) -> CaseRecord:
        data = self.client.get_sobject("Case", case_id, self.case_fields)
        return CaseRecord(
            id=data["Id"],
            case_number=data.get("CaseNumber") or "",
            subject=data.get("Subject") or "",
            description=data.get("Description"),
            created_date=datetime.fromisoformat(data["CreatedDate"].replace("Z", "+00:00")),
            status=data.get("Status"),
        )

    def get_work_orders_for_case(self, case_id: str) -> list[WorkOrderRecord]:
        # RecordType.Name / Relevant Department 커스텀 필드명은 설정으로 교체 가능하도록 후속 확장
        # MVP: SOQL은 어댑터 호출 측에서 mock 가능; 여기선 query 결과를 매핑
        soql = (
            f"SELECT Id, WorkOrderNumber, Subject, CreatedDate, CaseId, Priority, "
            f"{self.activities_field}, RecordType.Name FROM WorkOrder WHERE CaseId = '{case_id}'"
        )
        data = self.client.query(soql)
        out: list[WorkOrderRecord] = []
        for row in data.get("records", []):
            created = row.get("CreatedDate")
            out.append(
                WorkOrderRecord(
                    id=row["Id"],
                    work_order_number=row.get("WorkOrderNumber") or "",
                    record_type=(row.get("RecordType") or {}).get("Name") or "",
                    subject=row.get("Subject"),
                    activities=row.get(self.activities_field),
                    case_id=row.get("CaseId"),
                    created_date=datetime.fromisoformat(created.replace("Z", "+00:00")) if created else None,
                    priority=row.get("Priority"),
                )
            )
        return out
```

> 구현 시 Relevant Department 커스텀 필드 API 이름은 `settings`에 `wo_department_field`로 두고 SOQL에 포함하도록 Task 8 커밋 직후 작은 후속 커밋으로 넣어도 된다. 테스트는 안전 가드가 핵심이다.

- [ ] **Step 4: 통과 확인** — `pytest tests/test_sf_adapter_safety.py -v`

- [ ] **Step 5: 커밋**

```bash
git add src/ai_work_automation/sf tests/test_sf_adapter_safety.py
git commit -m "feat: Salesforce 어댑터와 Activities 쓰기 안전 가드 추가"
```

---

### Task 9: 파이프라인 오케스트레이션

**Files:**
- Create: `src/ai_work_automation/pipeline.py`
- Create: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: OptInStore, Settings, SalesforceAdapter, PmsConnector, routes, gate
- Produces: `run_case_automation(case_id, ...) -> PipelineResult`

- [ ] **Step 1: 실패 테스트**

```python
# tests/test_pipeline.py
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from ai_work_automation.job_log import JobLogStore
from ai_work_automation.models import CaseRecord, ConnectorResult, DraftContent, WorkOrderRecord
from ai_work_automation.opt_in import OptInStore
from ai_work_automation.pipeline import PipelineResult, run_case_automation
from ai_work_automation.router import RouteRule, RouteWhen


def _routes():
    return [
        RouteRule(
            id="voc-sw-pms",
            when=RouteWhen(recordType="VOC", department="SW"),
            targets=["pms"],
        )
    ]


def test_skip_when_not_selected(tmp_path: Path, sample_case, sample_wo_voc_sw):
    opt = OptInStore(tmp_path / "opt.json")
    log = JobLogStore(tmp_path / "log.jsonl")
    sf = MagicMock()
    result = run_case_automation(
        case_id=sample_case.id,
        opt_in=opt,
        job_log=log,
        sf=sf,
        routes=_routes(),
        pms=MagicMock(),
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        pms_project_id=1,
        approve_fn=lambda d: True,
    )
    assert result.status == "skipped"
    assert result.reason == "not_selected"
    sf.get_case.assert_not_called()


def test_happy_path_pms_writeback(tmp_path: Path, sample_case, sample_wo_voc_sw):
    opt = OptInStore(tmp_path / "opt.json")
    opt.select(sample_case.id)
    log = JobLogStore(tmp_path / "log.jsonl")
    sf = MagicMock()
    sf.get_case.return_value = sample_case
    sf.get_work_orders_for_case.return_value = [sample_wo_voc_sw]
    pms = MagicMock()
    pms.create.return_value = ConnectorResult(
        ok=True, ref="4710", url="https://pms.example/issues/4710"
    )
    result = run_case_automation(
        case_id=sample_case.id,
        opt_in=opt,
        job_log=log,
        sf=sf,
        routes=_routes(),
        pms=pms,
        cutoff=datetime(2026, 12, 1, tzinfo=timezone.utc),
        pms_project_id=1,
        approve_fn=lambda d: True,
    )
    assert result.status == "success"
    sf.append_work_order_activities.assert_called_once()
    args, kwargs = sf.append_work_order_activities.call_args
    assert "PMS – https://pms.example/issues/4710" in args[1]
```

- [ ] **Step 2: 실패 확인** — `pytest tests/test_pipeline.py -v`

- [ ] **Step 3: 구현**

```python
# src/ai_work_automation/pipeline.py
from collections.abc import Callable
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from ai_work_automation.cutoff import is_after_cutoff
from ai_work_automation.draft_template import build_pms_draft
from ai_work_automation.job_log import JobLogStore
from ai_work_automation.models import DraftContent
from ai_work_automation.opt_in import OptInStore
from ai_work_automation.router import RouteRule, resolve_targets


class PipelineResult(BaseModel):
    status: str
    reason: str | None = None
    case_id: str
    details: dict[str, Any] | None = None


def run_case_automation(
    *,
    case_id: str,
    opt_in: OptInStore,
    job_log: JobLogStore,
    sf: Any,
    routes: list[RouteRule],
    pms: Any,
    cutoff: datetime,
    pms_project_id: int,
    approve_fn: Callable[[DraftContent], bool],
) -> PipelineResult:
    if not opt_in.is_selected(case_id):
        result = PipelineResult(status="skipped", reason="not_selected", case_id=case_id)
        job_log.append(result.model_dump())
        return result

    case = sf.get_case(case_id)
    if not is_after_cutoff(case.created_date, cutoff):
        result = PipelineResult(status="skipped", reason="before_cutoff", case_id=case_id)
        job_log.append(result.model_dump())
        return result

    work_orders = sf.get_work_orders_for_case(case_id)
    acted = []
    for wo in work_orders:
        targets = resolve_targets(wo, routes)
        if "pms" not in targets:
            continue
        if wo.created_date and not is_after_cutoff(wo.created_date, cutoff):
            continue
        draft = build_pms_draft(case, wo)
        if not approve_fn(draft):
            job_log.append(
                {"case_id": case_id, "work_order_id": wo.id, "status": "rejected_by_human"}
            )
            continue
        # 멱등: Activities에 이미 PMS URL이 있으면 스킵
        if wo.activities and "PMS – " in wo.activities and "pms." in wo.activities.lower():
            job_log.append(
                {"case_id": case_id, "work_order_id": wo.id, "status": "skipped", "reason": "already_linked"}
            )
            continue
        conn_result = pms.create(draft, project_id=pms_project_id)
        if not conn_result.ok:
            job_log.append(
                {
                    "case_id": case_id,
                    "work_order_id": wo.id,
                    "status": "failed",
                    "error": conn_result.error,
                }
            )
            continue
        line = f"PMS – {conn_result.url}"
        sf.append_work_order_activities(wo, line, case_selected=True)
        acted.append({"work_order_id": wo.id, "url": conn_result.url})

    status = "success" if acted else "noop"
    result = PipelineResult(status=status, case_id=case_id, details={"acted": acted})
    job_log.append(result.model_dump())
    return result
```

- [ ] **Step 4: 통과 확인** — `pytest tests/test_pipeline.py -v`

- [ ] **Step 5: 커밋**

```bash
git add src/ai_work_automation/pipeline.py tests/test_pipeline.py
git commit -m "feat: Case 자동화 파이프라인(옵트인·PMS·회수) 추가"
```

---

### Task 10: CLI + 환경 예시 + 전체 테스트

**Files:**
- Create: `src/ai_work_automation/cli.py`
- Create: `.env.example`
- Create: `README.md` (한국어, 실행 방법만)
- Modify: `config/settings.example.yaml` (필요 시 `pms_project_id` 추가)

**Interfaces:**
- Produces: CLI 명령 `select`, `deselect`, `list`, `run`

- [ ] **Step 1: settings에 pms_project_id 필드 추가 테스트/반영**

`Settings`에 `pms_project_id: int = 1`, `wo_department_field: str = "Relevant_Department__c"` 추가 (실제 API 이름은 배포 전 Describe로 교체).

- [ ] **Step 2: CLI 구현**

```python
# src/ai_work_automation/cli.py
import os
from datetime import datetime
from pathlib import Path

import httpx
import typer
from dotenv import load_dotenv

from ai_work_automation.gate.human import human_approve
from ai_work_automation.job_log import JobLogStore
from ai_work_automation.opt_in import OptInStore
from ai_work_automation.pipeline import run_case_automation
from ai_work_automation.router import load_routes
from ai_work_automation.settings import load_settings
from ai_work_automation.connectors.pms import PmsConnector
from ai_work_automation.sf.adapter import SalesforceAdapter
from ai_work_automation.sf.client import SalesforceHttpClient

app = typer.Typer(help="AI 업무 자동화 CLI (MVP)")
load_dotenv()


def _settings(path: Path):
    return load_settings(path)


@app.command("select")
def select_case(case_id: str, settings: Path = typer.Option(Path("config/settings.yaml"))):
    s = _settings(settings)
    OptInStore(s.opt_in_path).select(case_id)
    typer.echo(f"선택됨: {case_id}")


@app.command("deselect")
def deselect_case(case_id: str, settings: Path = typer.Option(Path("config/settings.yaml"))):
    s = _settings(settings)
    OptInStore(s.opt_in_path).deselect(case_id)
    typer.echo(f"선택 해제: {case_id}")


@app.command("list-selected")
def list_selected(settings: Path = typer.Option(Path("config/settings.yaml"))):
    s = _settings(settings)
    for cid in OptInStore(s.opt_in_path).list_selected():
        typer.echo(cid)


@app.command("run")
def run(
    case_id: str,
    settings: Path = typer.Option(Path("config/settings.yaml")),
    yes: bool = typer.Option(False, "--yes", help="Human Gate 자동 승인(테스트용)"),
):
    s = _settings(settings)
    opt = OptInStore(s.opt_in_path)
    log = JobLogStore(s.job_log_path)
    routes = load_routes(s.routes_path)

    instance = os.environ[s.sf_instance_url_env]
    token = os.environ[s.sf_access_token_env]
    sf_client = SalesforceHttpClient(instance, token)
    sf = SalesforceAdapter(client=sf_client, cutoff=s.automation_enabled_after)

    pms_key = os.environ[s.pms_api_key_env]
    http = httpx.Client(base_url=s.pms_base_url, timeout=60.0)
    pms = PmsConnector(client=http, api_key=pms_key, base_url=s.pms_base_url)

    approve = (lambda d: True) if yes else human_approve
    result = run_case_automation(
        case_id=case_id,
        opt_in=opt,
        job_log=log,
        sf=sf,
        routes=routes,
        pms=pms,
        cutoff=s.automation_enabled_after,
        pms_project_id=s.pms_project_id,
        approve_fn=approve,
    )
    typer.echo(result.model_dump_json(ensure_ascii=False, indent=2))


if __name__ == "__main__":
    app()
```

`.env.example`:

```env
SF_INSTANCE_URL=https://parksystems.my.salesforce.com
SF_ACCESS_TOKEN=
PMS_API_KEY=
```

`README.md` (한국어): 설치, `config/settings.yaml` 복사, 옵트인, `ai-work run`, 안전 규칙 요약.

- [ ] **Step 3: 전체 테스트**

Run: `pytest -v`  
Expected: 모든 테스트 PASS

- [ ] **Step 4: 수동 스모크 (자격 있을 때)**

1. `config/settings.example.yaml` → `config/settings.yaml` 복사, 컷오프를 미래/과거로 시험  
2. `ai-work select <새_테스트_Case_Id>`  
3. `ai-work run <Id>` — Human Gate에서 내용 확인 후 `y`  
4. 컷오프 이전 Case Id로 run → skipped, SF PATCH 없음  

- [ ] **Step 5: 커밋**

```bash
git add src/ai_work_automation/cli.py src/ai_work_automation/settings.py .env.example README.md config
git commit -m "feat: MVP CLI(select/run)와 환경 예시 추가"
```

---

## 셀프 리뷰 (계획 vs 스펙)

| 스펙 요구 | 대응 Task |
|-----------|-----------|
| 옵트인 선택 | Task 3, 10 |
| 컷오프 / 기존 건 미수정 | Task 2, 8, 9 |
| SF 읽기 + Activities 회수 | Task 8, 9 |
| 라우팅 VOC+SW→PMS | Task 4, 9 |
| Human Gate | Task 6, 9, 10 |
| PMS 게시 + URL 회수 | Task 7, 9 |
| 작업 로그 | Task 5, 9 |
| Outlook / Workful / Teams / RN | **이 계획 범위 밖** (후속) |
| Draft AI(LLM) | 템플릿으로 대체 (후속) |
| 한국어 문서 | README + 본 계획 |

플레이스홀더·TBD 문구 없음. 타입명(`ConnectorResult`, `PipelineResult`, `OptInStore`)은 Task 간 일치.

---

## 후속 계획 (참고만, 이 파일에서 구현하지 않음)

1. `…-outlook-technical-support.md` — Graph 메일 초안  
2. `…-workful-teams.md` — Dataverse/Teams  
3. `…-release-notes.md` — 메일→RN  
4. OAuth 토큰 자동 발급, Relevant Department SOQL 필드 확정, LLM 초안
