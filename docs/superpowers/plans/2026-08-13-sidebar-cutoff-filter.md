# Sidebar Cutoff Date Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 사이드바에서 컷오프 날짜를 바꾸고 `automation_enabled_after`를 yaml에 즉시 저장해 스캔에 반영한다.

**Architecture:** `format_cutoff_iso_kst(date) -> str` 헬퍼 + `webui` 사이드바 `date_input`. 변경 시 `update_settings_yaml` 후 `st.rerun()`으로 `_settings()`가 새 값을 읽게 한다.

**Tech Stack:** Python 3.11+, Streamlit, PyYAML, pytest

**Spec:** `docs/superpowers/specs/2026-08-13-sidebar-cutoff-filter-design.md`

## Global Constraints

- 사이드바만 (설정 탭 중복 없음)
- 시각 고정: `T00:00:00+09:00`
- 변경 시 `config/settings.yaml`의 `automation_enabled_after` 즉시 저장
- Caption: 미래 날짜면 0건일 수 있음 / yaml 저장 안내
- 커밋은 사용자 요청 시에만

## File map

| File | Responsibility |
|------|----------------|
| `src/ai_work_automation/config_store.py` | `format_cutoff_iso_kst` |
| `tests/test_config_store.py` | 헬퍼 단위 테스트 |
| `src/ai_work_automation/webui.py` | 사이드바 date_input + 저장 |
| `config/settings.example.yaml` | 주석 한 줄 (선택) |

---

### Task 1: `format_cutoff_iso_kst`

**Files:** Modify `config_store.py`, `tests/test_config_store.py`

**Interfaces:**
- Produces: `format_cutoff_iso_kst(d: date) -> str` → `"YYYY-MM-DDT00:00:00+09:00"`

- [ ] **Step 1: Failing test**

```python
from datetime import date
from ai_work_automation.config_store import format_cutoff_iso_kst

def test_format_cutoff_iso_kst() -> None:
    assert format_cutoff_iso_kst(date(2026, 1, 1)) == "2026-01-01T00:00:00+09:00"
```

- [ ] **Step 2: Implement**

```python
from datetime import date

def format_cutoff_iso_kst(d: date) -> str:
    return f"{d.isoformat()}T00:00:00+09:00"
```

- [ ] **Step 3: pytest tests/test_config_store.py -v** → PASS

---

### Task 2: Sidebar date_input + save

**Files:** Modify `webui.py` sidebar (필터 섹션, Relevant Department 위)

- [ ] Import `format_cutoff_iso_kst`, `update_settings_yaml`
- [ ] `date_input` key=`sidebar_cutoff_date`; 세션 미초기화면 settings 날짜(KST)로 초기화
- [ ] caption 안내
- [ ] 값이 settings 날짜와 다르면 yaml 저장 후 `st.rerun()`
- [ ] example yaml에 사이드바 변경 가능 주석 한 줄

- [ ] Manual: 컷오프를 과거로 → 스캔 0건이 아닐 수 있음
