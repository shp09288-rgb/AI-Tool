# Final fix report — tool-first VOC Important findings

**Status:** DONE  
**Commit:** `fix(voc): Activities 컷오프 우회와 부분 성공 시 ID 표시`  
**Tests:** `pytest tests/test_tool_first_voc.py -q` → 10 passed  
**Path:** `.worktrees/tool-first-voc`

## Important #1

- `append_work_order_activities` now has `enforce_cutoff: bool = True` (same pattern as Case Activities).
- Fresh VOC WO appends with `enforce_cutoff=False` so a future cutoff (e.g. Dec 2026) cannot fail after Case/WO/PMS already exist.
- Activities failure is caught: result stays `ok=True` with warning plus Case/WO/PMS ids and links.
- Unexpected errors after partial create return `ok=False` with ids instead of raising.
- VOC execute except handlers still render any ids attached to the exception.

## Important #2

- VOC tab shows Salesforce summary (mode, title, department, Case, Asset, SID) above the PMS HTML preview, before/when preview runs.
