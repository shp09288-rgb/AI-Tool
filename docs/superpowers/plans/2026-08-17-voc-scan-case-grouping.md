# VOC Scan Case Grouping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** VOC→PMS 스캔에서 미연동 WO를 Case 단위로 묶어 기본 선택하고, 필요 시 WO 개별 선택을 유지한다.

**Architecture:** `scan_candidates`는 그대로 둔다. 순수 헬퍼 `group_unlinked_by_case`가 `ScanRow` 목록을 `CaseScanGroup`으로 묶는다. Streamlit 스캔 탭은 Case/WO 선택 모드 토글과 Case 요약 표시만 추가하고, 등록은 기존 `_process_selection`에 `list[ScanRow]`를 넘긴다.

**Tech Stack:** Python 3.11+, Pydantic, Streamlit, pytest

**Spec:** `docs/superpowers/specs/2026-08-17-voc-scan-case-grouping-design.md`

## Global Constraints

- SF SOQL / `scan_candidates` 시그니처 변경 금지 (후처리 그룹만)
- 연동된 WO는 선택·등록 대상에 넣지 않음
- 기본 선택 모드 = Case 단위; WO 개별 모드 유지
- 사이드바 미연동/내 담당 기본 필터·프리셋 비범위
- Tool-first VOC 탭 비범위
- 커밋은 사용자 요청 시에만 (plan commit step skip)

## File map

| File | Responsibility |
|------|----------------|
| `src/ai_work_automation/services.py` | `CaseScanGroup`, `group_unlinked_by_case`, (optional) label helper |
| `tests/test_services.py` | 그룹 헬퍼 단위 테스트 |
| `src/ai_work_automation/webui.py` | tab_scan: 요약·Case 표·모드 토글·선택 flatten |

---

### Task 1: `CaseScanGroup` + `group_unlinked_by_case`

**Files:**
- Modify: `src/ai_work_automation/services.py`
- Test: `tests/test_services.py`

**Interfaces:**
- Produces:

```python
class CaseScanGroup(BaseModel):
    case_id: str
    case_number: str
    case_subject: str
    case_owner_name: str = ""
    unlinked: list[ScanRow]
    linked_count: int = 0

def group_unlinked_by_case(rows: list[ScanRow]) -> list[CaseScanGroup]:
    """Group scan rows by case; unlinked only in .unlinked; sort by newest unlinked created_date desc."""

def case_group_label(group: CaseScanGroup, *, title_max: int = 40) -> str:
    """Return '{case_number} · 미연동 {k}건 · {title}' for multiselect."""
```

- Group key: `case_id` if non-empty else `case_number`
- Metadata (`case_subject`, `case_owner_name`, `case_id`, `case_number`) from first row seen in that key (prefer an unlinked row if any)
- `linked_count`: count of rows with `linked=True` for that key
- Groups with `unlinked == []` are **omitted** from the returned list (only cases with ≥1 unlinked appear in selection)
- Sort: max(`created_date` among unlinked) descending; empty dates sort last
- Representative title for label: newest unlinked row's `title`

- [ ] **Step 1: Write failing tests** in `tests/test_services.py`

```python
from ai_work_automation.services import CaseScanGroup, ScanRow, group_unlinked_by_case, case_group_label

def _row(**kwargs) -> ScanRow:
    data = dict(
        case_id="500A",
        case_number="00183895",
        case_subject="Subject",
        work_order_id="0WO1",
        work_order_number="00025526",
        title="VOC A",
        created_date="2026-08-12T10:00:00+00:00",
        linked=False,
        selected=False,
    )
    data.update(kwargs)
    return ScanRow(**data)


def test_group_same_case_two_unlinked_into_one_group():
    rows = [
        _row(work_order_id="0WO1", work_order_number="00025526", title="First",
             created_date="2026-08-12T09:00:00+00:00"),
        _row(work_order_id="0WO2", work_order_number="00025527", title="Second",
             created_date="2026-08-12T11:00:00+00:00"),
    ]
    groups = group_unlinked_by_case(rows)
    assert len(groups) == 1
    assert len(groups[0].unlinked) == 2
    assert groups[0].linked_count == 0
    assert case_group_label(groups[0]).startswith("00183895 · 미연동 2건 ·")


def test_group_counts_linked_but_excludes_from_unlinked():
    rows = [
        _row(work_order_id="0WO1", linked=False),
        _row(work_order_id="0WO2", work_order_number="00025527", linked=True,
             created_date="2026-08-12T12:00:00+00:00"),
    ]
    groups = group_unlinked_by_case(rows)
    assert len(groups) == 1
    assert len(groups[0].unlinked) == 1
    assert groups[0].linked_count == 1


def test_group_key_falls_back_to_case_number_when_case_id_empty():
    rows = [
        _row(case_id="", case_number="00190001", work_order_id="0WO1"),
        _row(case_id="", case_number="00190001", work_order_id="0WO2",
             work_order_number="0002"),
    ]
    groups = group_unlinked_by_case(rows)
    assert len(groups) == 1
    assert groups[0].case_number == "00190001"


def test_group_omits_cases_with_only_linked_rows():
    rows = [_row(linked=True)]
    assert group_unlinked_by_case(rows) == []


def test_groups_sorted_by_newest_unlinked_created_date_desc():
    older = _row(case_id="500OLD", case_number="00100001",
                 created_date="2026-01-01T00:00:00+00:00")
    newer = _row(case_id="500NEW", case_number="00100002",
                 created_date="2026-08-15T00:00:00+00:00")
    groups = group_unlinked_by_case([older, newer])
    assert [g.case_id for g in groups] == ["500NEW", "500OLD"]
```

- [ ] **Step 2: Run** `python -m pytest tests/test_services.py::test_group_same_case_two_unlinked_into_one_group tests/test_services.py::test_group_counts_linked_but_excludes_from_unlinked tests/test_services.py::test_group_key_falls_back_to_case_number_when_case_id_empty tests/test_services.py::test_group_omits_cases_with_only_linked_rows tests/test_services.py::test_groups_sorted_by_newest_unlinked_created_date_desc -v` → FAIL (missing symbols)

- [ ] **Step 3: Implement** `CaseScanGroup`, `group_unlinked_by_case`, `case_group_label` in `services.py`

- [ ] **Step 4: Run** `python -m pytest tests/test_services.py -q` → PASS (existing + new)

- [ ] **Step 5: Commit** — skip unless user asks

---

### Task 2: Streamlit 「VOC→PMS」 Case/WO 선택 UI

**Files:**
- Modify: `src/ai_work_automation/webui.py` (`with tab_scan:` block ~1898–1959)
- Test: none required beyond Task 1; manual smoke checklist below

**Interfaces:**
- Consumes: `group_unlinked_by_case`, `case_group_label`, `CaseScanGroup` from `services`
- Produces: UI behavior only; still calls `_process_selection(s, targets: list[ScanRow], ...)`

- [ ] **Step 1: Import helpers** at top of webui (extend existing services import):

```python
from ai_work_automation.services import (
    case_group_label,
    group_unlinked_by_case,
    scan_candidates,
    status_overview,
)
```

- [ ] **Step 2: After `rows = st.session_state.get("scan_rows")` and `unlinked = ...`**, compute:

```python
groups = group_unlinked_by_case(rows)
st.caption(
    f"전체 {len(rows)}건 중 PMS 미연동 {len(unlinked)}건 · 미연동 Case {len(groups)}건 "
    f"(컷오프 이후 생성분)"
)
```

- [ ] **Step 3: Case 요약 표** (replace or sit above existing WO dataframe)

Show dataframe of:

```python
[
    {
        "케이스": g.case_number,
        "케이스 담당자": g.case_owner_name,
        "미연동 WO": len(g.unlinked),
        "연동 WO": g.linked_count,
        "제목": (g.unlinked[0].title if g.unlinked else g.case_subject)[:60],
        "최신 생성일": max((r.created_date[:10] for r in g.unlinked if r.created_date), default=""),
    }
    for g in groups
]
```

Keep a **checkbox or expander** “WO 상세 표 보기” that shows the existing per-WO dataframe (all `rows`) so detail is not lost. Default: Case 요약만 보이게.

- [ ] **Step 4: Selection section**

```python
st.subheader("등록할 대상 선택")
mode = st.radio(
    "선택 단위",
    ["Case 단위", "WO 개별"],
    horizontal=True,
    key="scan_select_mode",
    index=0,  # Case default
)
if not groups:
    st.info("미연동 후보가 없습니다.")
else:
    if mode == "Case 단위":
        options = {case_group_label(g): g for g in groups}
        picked = st.multiselect("Case", list(options.keys()), key="scan_case_pick")
        targets = [row for label in picked for row in options[label].unlinked]
    else:
        options = {
            f"{r.case_number} / WO {r.work_order_number} / {r.title[:45]}": r
            for r in unlinked
        }
        picked = st.multiselect("워크오더", list(options.keys()), key="scan_wo_pick")
        targets = [options[label] for label in picked]
    # existing issue_type radio + _process_selection when targets
```

Preserve existing issue type radio keys / `_process_selection` call pattern.

- [ ] **Step 5: Run** `python -m pytest tests/test_services.py tests/test_cli.py -q` → PASS

- [ ] **Step 6: Manual smoke**
  - 스캔 후 Case 요약에 미연동 Case 수 표시
  - 동일 Case 2 WO → Case 모드 옵션 1개, 선택 시 targets 2
  - WO 개별 모드 → 옵션 2개

- [ ] **Step 7: Commit** — skip unless user asks

---

## Spec coverage (self-review)

| Spec | Task |
|------|------|
| group helper + CaseScanGroup | Task 1 |
| caption 미연동 Case G건 | Task 2 |
| Case 요약 표 + WO 상세 optional | Task 2 |
| Case 기본 / WO 개별 토글 | Task 2 |
| flatten → `_process_selection` | Task 2 |
| 비범위 B/프리셋/SF | 미구현 |

## Type consistency

- `CaseScanGroup`, `group_unlinked_by_case`, `case_group_label` names match across tasks
- `_process_selection` still receives `list[ScanRow]`
