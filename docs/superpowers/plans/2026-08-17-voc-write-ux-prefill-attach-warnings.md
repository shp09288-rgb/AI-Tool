# VOC Write UX Prefill + Attach Warnings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Case 조회/VOC WO 생성 시 형제 WO에서 AssetId·SID를 비어 있는 칸에만 채우고, SF 파일 첨부 실패는 `warnings`로 UI에 보여 준다.

**Architecture:** 순수 함수 `resolve_asset_hints`가 Case + 형제 WO 힌트 목록에서 payload 폴백 값을 고른다. SF 어댑터는 힌트 전용 경량 SOQL만 제공한다. 오케스트레이터는 create 직전 힌트를 재계산하고, `_best_effort_attach`는 실패를 `warnings`로 모아 `ToolFirstVocResult`에 실는다. UI는 조회 시 빈 칸만 프리필하고 결과 경고를 표시한다.

**Tech Stack:** Python 3.11+, pytest, Streamlit, 기존 SF adapter/client

**Spec:** `docs/superpowers/specs/2026-08-17-voc-write-ux-prefill-attach-warnings-design.md`

## Global Constraints

- 첨부 실패로 전체 실행을 실패 처리하지 않음 (`ok=True` 유지 가능, `warnings`만)
- Quill 붙여넣기 이미지·드래그 크롭은 비범위
- `WorkOrderRecord` 전역 스키마 확장은 필수 아님 — 힌트 전용 타입/SOQL 사용
- payload에 값이 있으면 힌트보다 **항상 우선**
- UI 프리필은 세션 칸이 **비어 있을 때만**
- 커밋은 사용자 요청 시에만 (plan Step의 commit은 skip)

## File map

| File | Responsibility |
|------|----------------|
| `src/ai_work_automation/tool_first_voc.py` | `WorkOrderAssetHint`, `resolve_asset_hints`, SID/Asset 폴백, attach→warnings |
| `src/ai_work_automation/sf/adapter.py` | `list_work_order_asset_hints(case_id)` 경량 SOQL |
| `tests/test_tool_first_voc.py` | 힌트 우선순위·SID 폴백·warnings |
| `tests/test_sf_voc_create.py` (또는 신규) | adapter 힌트 조회 SOQL/매핑 |
| `src/ai_work_automation/webui.py` | 조회 프리필 + `_render_voc_result` warnings |

---

### Task 1: `resolve_asset_hints` + SF 힌트 조회

**Files:**
- Modify: `src/ai_work_automation/tool_first_voc.py`
- Modify: `src/ai_work_automation/sf/adapter.py`
- Test: `tests/test_tool_first_voc.py`
- Test: `tests/test_sf_voc_create.py` (기존 파일이 있으면 이어서; 없으면 같은 파일에 추가)

**Interfaces:**
- Produces:

```python
@dataclass(frozen=True)
class WorkOrderAssetHint:
    asset_id: str | None = None
    asset_sid: str | None = None
    created_date: datetime | None = None


@dataclass(frozen=True)
class AssetHints:
    asset_id: str | None = None
    asset_sid: str | None = None


def resolve_asset_hints(
    case: CaseRecord | None,
    work_orders: list[WorkOrderAssetHint],
) -> AssetHints:
    """Case.AssetId first, then newest WO AssetId; SID from newest WO with SID."""
    ...


# SalesforceAdapter
def list_work_order_asset_hints(self, case_id: str) -> list[WorkOrderAssetHint]:
    """SELECT Id, AssetId, Asset_SID__c, CreatedDate FROM WorkOrder WHERE CaseId=... ORDER BY CreatedDate DESC"""
```

- [ ] **Step 1: Write failing unit tests for `resolve_asset_hints`**

```python
from datetime import datetime, timezone
from ai_work_automation.tool_first_voc import (
    AssetHints,
    WorkOrderAssetHint,
    resolve_asset_hints,
)

def test_resolve_prefers_case_asset_id_over_wo():
    case = _case(asset_id="02iCASE")
    wos = [
        WorkOrderAssetHint(
            asset_id="02iWO",
            asset_sid="SID-WO",
            created_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
    ]
    assert resolve_asset_hints(case, wos) == AssetHints(
        asset_id="02iCASE", asset_sid="SID-WO"
    )


def test_resolve_uses_newest_wo_when_case_has_no_asset():
    case = _case(asset_id=None)
    older = WorkOrderAssetHint(
        asset_id="02iOLD",
        asset_sid="SID-OLD",
        created_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer = WorkOrderAssetHint(
        asset_id="02iNEW",
        asset_sid="SID-NEW",
        created_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    assert resolve_asset_hints(case, [older, newer]) == AssetHints(
        asset_id="02iNEW", asset_sid="SID-NEW"
    )


def test_resolve_sid_from_wo_even_if_asset_from_case():
    case = _case(asset_id="02iCASE")
    wos = [
        WorkOrderAssetHint(
            asset_id=None,
            asset_sid="NX-10",
            created_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
    ]
    assert resolve_asset_hints(case, wos).asset_sid == "NX-10"
```

- [ ] **Step 2: Run tests — expect FAIL (import / missing symbols)**

Run: `python -m pytest tests/test_tool_first_voc.py::test_resolve_prefers_case_asset_id_over_wo tests/test_tool_first_voc.py::test_resolve_uses_newest_wo_when_case_has_no_asset tests/test_tool_first_voc.py::test_resolve_sid_from_wo_even_if_asset_from_case -v`

- [ ] **Step 3: Implement `WorkOrderAssetHint`, `AssetHints`, `resolve_asset_hints` in `tool_first_voc.py`**

규칙:
- `asset_id`: `case.asset_id` if set; else first non-empty among WOs sorted by `created_date` desc (None dates last)
- `asset_sid`: first non-empty `asset_sid` among WOs sorted the same way (Case has no SID)

- [ ] **Step 4: Implement `SalesforceAdapter.list_work_order_asset_hints`**

```python
def list_work_order_asset_hints(self, case_id: str) -> list[WorkOrderAssetHint]:
    from ai_work_automation.tool_first_voc import WorkOrderAssetHint  # or move type to models/sf to avoid cycle — prefer define hint dataclass in tool_first_voc and import in adapter; if cycle, put dataclasses in tool_first_voc and have adapter return list[dict] mapped by caller. Preferred: put WorkOrderAssetHint in tool_first_voc; adapter imports it (adapter already imports models; tool_first_voc imports adapter types only at runtime in run — check cycles).

    soql = (
        "SELECT Id, AssetId, Asset_SID__c, CreatedDate FROM WorkOrder "
        f"WHERE CaseId = '{_soql_escape(case_id)}' "
        "ORDER BY CreatedDate DESC"
    )
    rows = self.client.query(soql).get("records", [])
    out: list[WorkOrderAssetHint] = []
    for row in rows:
        created = row.get("CreatedDate")
        created_dt = (
            datetime.fromisoformat(created.replace("Z", "+00:00"))
            if created
            else None
        )
        out.append(
            WorkOrderAssetHint(
                asset_id=row.get("AssetId") or None,
                asset_sid=row.get("Asset_SID__c") or None,
                created_date=created_dt,
            )
        )
    return out
```

If import cycle: define `WorkOrderAssetHint` / `AssetHints` / `resolve_asset_hints` in new thin module `src/ai_work_automation/asset_hints.py` and import from both. Prefer that if `adapter` ↔ `tool_first_voc` cycle appears.

- [ ] **Step 5: Adapter unit test (mock client.query)**

```python
def test_list_work_order_asset_hints_maps_rows():
    # fake client returns one row with AssetId, Asset_SID__c, CreatedDate
    # assert hint fields and SOQL contains Asset_SID__c and CaseId
```

- [ ] **Step 6: Run** `python -m pytest tests/test_tool_first_voc.py tests/test_sf_voc_create.py -q` → PASS for new + existing

- [ ] **Step 7: Commit** — skip unless user asks

---

### Task 2: 오케스트레이터 — SID/Asset 폴백 + attach `warnings`

**Files:**
- Modify: `src/ai_work_automation/tool_first_voc.py`
- Test: `tests/test_tool_first_voc.py`

**Interfaces:**
- Consumes: `resolve_asset_hints`, `sf.list_work_order_asset_hints` (existing_case path already has `get_work_orders_for_case` — also call `list_work_order_asset_hints` or replace SID needs with hints list; for create use hints)
- Produces:
  - `ToolFirstVocResult.warnings: list[str]` (default `[]`)
  - `_best_effort_attach(...) -> list[str]` (warning strings)
  - `_wo_fields` / resolve path applies payload-or-hints for both AssetId and Asset_SID__c

- [ ] **Step 1: Failing tests**

```python
def test_existing_case_copies_sibling_sid_onto_wo_when_payload_omits_it():
    case = _case(asset_id="02iCASE")
    sf = _sf(case=case, existing_wos=[])
    sf.list_work_order_asset_hints.return_value = [
        WorkOrderAssetHint(
            asset_id=None,
            asset_sid="NX-10",
            created_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )
    ]
    pms = MagicMock()
    pms.create.return_value = ConnectorResult(
        ok=True, ref="4710", url="https://pms.example/issues/4710"
    )
    result = run_tool_first_voc(
        sf, pms, _settings(), _payload(asset_id=None, asset_sid=None),
        dry_run=False, approved=True,
    )
    assert result.ok is True
    fields = sf.create_voc_work_order.call_args.kwargs["fields"]
    assert fields["AssetId"] == "02iCASE"
    assert fields["Asset_SID__c"] == "NX-10"


def test_payload_sid_wins_over_sibling_hint():
    case = _case(asset_id=None)
    sf = _sf(case=case, existing_wos=[])
    sf.list_work_order_asset_hints.return_value = [
        WorkOrderAssetHint(asset_sid="FROM-WO", created_date=datetime(2026, 8, 1, tzinfo=timezone.utc))
    ]
    pms = MagicMock()
    pms.create.return_value = ConnectorResult(
        ok=True, ref="4710", url="https://pms.example/issues/4710"
    )
    run_tool_first_voc(
        sf, pms, _settings(), _payload(asset_sid="FROM-UI"),
        dry_run=False, approved=True,
    )
    fields = sf.create_voc_work_order.call_args.kwargs["fields"]
    assert fields["Asset_SID__c"] == "FROM-UI"


def test_attach_failure_sets_warnings_but_keeps_ok():
    case = _case()
    sf = _sf(case=case, existing_wos=[])
    sf.list_work_order_asset_hints.return_value = []
    sf.client.create_content_version_from_bytes.side_effect = RuntimeError("boom")
    pms = MagicMock()
    pms.create.return_value = ConnectorResult(
        ok=True, ref="4710", url="https://pms.example/issues/4710"
    )
    result = run_tool_first_voc(
        sf,
        pms,
        _settings(),
        _payload(attachment_files=[("shot.png", b"abc")]),
        dry_run=False,
        approved=True,
    )
    assert result.ok is True
    assert result.warnings
    assert any("shot.png" in w for w in result.warnings)
```

Update `_sf` helper to default `list_work_order_asset_hints.return_value = []`.

Update `_result` / `ToolFirstVocResult` and all `_result(...)` / `_after_pms_write` call sites to accept/pass `warnings`.

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_tool_first_voc.py::test_existing_case_copies_sibling_sid_onto_wo_when_payload_omits_it tests/test_tool_first_voc.py::test_payload_sid_wins_over_sibling_hint tests/test_tool_first_voc.py::test_attach_failure_sets_warnings_but_keeps_ok -v`

- [ ] **Step 3: Implement**

1. Add `warnings: list[str] = field(default_factory=list)` to `ToolFirstVocResult`; thread through `_result` and `_after_pms_write`.
2. Replace `_resolve_asset_id` usage with:

```python
def _apply_asset_fields(
    payload: ToolFirstVocInput,
    hints: AssetHints,
) -> tuple[str | None, str | None]:
    asset_id = payload.asset_id or hints.asset_id
    asset_sid = payload.asset_sid or hints.asset_sid
    return asset_id, asset_sid
```

3. In `run_tool_first_voc`, after Case is known (existing found or new created), call:

```python
hint_rows = []
if case_id:
    list_fn = getattr(sf, "list_work_order_asset_hints", None)
    if list_fn is not None:
        hint_rows = list_fn(case_id)
hints = resolve_asset_hints(case, hint_rows)
# for new_case just created, siblings usually empty — still fine
```

Pass resolved ids into `_wo_fields` (extend signature to take `asset_id`/`asset_sid` overrides or `hints`).

4. `_best_effort_attach` → return `list[str]`; missing create method → one warning; per-file exception → warning with filename and short `str(exc)`; merge into result.warnings on success paths.

- [ ] **Step 4: Run full** `python -m pytest tests/test_tool_first_voc.py -q` → all PASS

- [ ] **Step 5: Commit** — skip unless user asks

---

### Task 3: Streamlit 조회 프리필 + 결과 warnings

**Files:**
- Modify: `src/ai_work_automation/webui.py` (`_render_voc_write_tab`, `_render_voc_result`)
- Test: optional thin test for pure helper if extracted; otherwise manual checklist below. Prefer extract:

```python
# in tool_first_voc or webui-adjacent helper
def empty_only_prefill(
    current_asset: str | None,
    current_sid: str | None,
    hints: AssetHints,
) -> tuple[str | None, str | None]:
    asset = current_asset or hints.asset_id
    sid = current_sid or hints.asset_sid
    return asset, sid
```

Unit-test that helper in `tests/test_tool_first_voc.py`.

- [ ] **Step 1: Test `empty_only_prefill`**

```python
def test_empty_only_prefill_does_not_overwrite():
    hints = AssetHints(asset_id="02iH", asset_sid="SID-H")
    assert empty_only_prefill("02iUSER", "", hints) == ("02iUSER", "SID-H")
    assert empty_only_prefill(None, "SID-USER", hints) == ("02iH", "SID-USER")
```

(Treat `""` as empty.)

- [ ] **Step 2: Implement helper + wire lookup in `_render_voc_write_tab`**

On successful `find_case_by_number`:
1. `hints_rows = sf.list_work_order_asset_hints(found.id)`
2. `hints = resolve_asset_hints(found, hints_rows)`
3. If `not (st.session_state.get("voc_write_asset") or "").strip()` and hints.asset_id → set session
4. Same for `voc_write_sid` / hints.asset_sid
5. Caption uses session values after prefill

- [ ] **Step 3: `_render_voc_result`**

```python
def _render_voc_result(result: ToolFirstVocResult) -> None:
    # existing success/warning/error for message
    ...
    for w in result.warnings or []:
        st.warning(w)
```

- [ ] **Step 4: Run** `python -m pytest tests/test_tool_first_voc.py tests/test_sf_voc_create.py -q` → PASS

- [ ] **Step 5: Manual smoke (optional)** — VOC 작성 → 기존 Case 조회 → SID 칸 채워짐; 첨부 실패 mock은 단위로 충분

- [ ] **Step 6: Commit** — skip unless user asks

---

## Spec coverage (self-review)

| Spec | Task |
|------|------|
| 4.1 우선순위 Case→newest WO | Task 1 `resolve_asset_hints` |
| 4.2 UI 빈 칸만 프리필 | Task 3 |
| 4.3 create 직전 재계산·payload 우선 | Task 2 |
| 5.x attach warnings + ok 유지 | Task 2 + Task 3 render |
| 비범위 C/D | 미구현 |

## Placeholder / type check

- `WorkOrderAssetHint` / `AssetHints` / `resolve_asset_hints` / `list_work_order_asset_hints` / `empty_only_prefill` / `warnings` names consistent across tasks
- Cycle risk: if adapter imports tool_first_voc, move hint types to `asset_hints.py`
