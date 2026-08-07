# Field Report Multi-Issue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Parse `□ 이슈 N (Case : ########)` lines from Daily Note into per-Case Activities and per-WO Start/End times with equal split defaults.

**Architecture:** Add issue parsing + slot splitting in `excel_ops.py`; extend `run_field_report` to loop `FieldIssue` payloads; rebuild WebUI WO section as common fields + per-issue rows. Single-issue sheets keep the legacy path.

**Tech Stack:** Python 3.11+, openpyxl, Streamlit, existing SalesforceAdapter, pytest.

## Global Constraints

- Case Activity = issue line only: `YYYY-MM-DD [FSE] □ … (Case : ########)`
- Default times = equal split of Excel L12–L13 (fallback 09:00–18:00)
- Overlap = warn only, do not block register
- Same cropped day-sheet xlsx attached to every WO
- No issue pattern → existing T9 + single summary flow

---

### Task 1: Parse issues + split slots

**Files:**
- Modify: `src/ai_work_automation/field_report/excel_ops.py`
- Test: `tests/test_field_report_excel.py`

**Produces:**
- `FieldIssue` dataclass
- `parse_field_issues(workbook_path, sheet_name, *, day, fse_name, work_start, work_end) -> list[FieldIssue]`
- `split_workday_slots(start: datetime, end: datetime, n: int) -> list[tuple[datetime, datetime]]`
- `find_time_overlaps(issues) -> list[str]` warnings

- [x] Write failing tests for parse (multi-line, fullwidth colon, no checkbox, none) and split (n=3, n=1)
- [x] Implement until green

### Task 2: Pipeline per-issue run

**Files:**
- Modify: `src/ai_work_automation/field_report/pipeline.py`
- Test: `tests/test_field_report_sf.py` (or new `tests/test_field_report_issues.py`)

**Produces:**
- `run_field_report(..., issues: list[FieldIssue] | None = None)`  
  If `issues` provided (included only), loop per issue with own activity/start/end; else legacy `case_ids` path.

- [x] Write failing dry-run mock test: 2 issues → different activities/times
- [x] Implement until green

### Task 3: WebUI per-WO settings

**Files:**
- Modify: `src/ai_work_automation/webui.py` (`_render_field_report_tab`)

**Produces:**
- Multi mode: common Status/Survey + per-issue include/Case/Activity/Start/End + overlap warning + resplit button
- Single mode: unchanged Case multiselect + common times
- Activity preview always uses current `fr_fse`

- [x] Wire parse on sheet load into session
- [x] Dry-run / real register use included issues
- [ ] Manual smoke: load sheet, adjust times, dry-run

### Task 4: Spec status + regression

- [x] Mark design doc status implemented
- [x] `pytest tests/test_field_report_*.py -q` all green
