# Tool-first VOC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tool 「VOC 작성」에서 신규/기존 Case로 VOC WO를 만들고, PMS는 미연동 시 이슈·연동 시 댓글로 처리한다 (본문은 PMS HTML 중심).

**Architecture:** SF 어댑터에 Case/WO create를 추가하고, `tool_first_voc` 오케스트레이터가 승인 후 SF→PMS→Activities를 순서 실행한다. UI는 Streamlit 새 탭 + 기존 Quill/미리보기 패턴. 이미지 크롭·첨부는 PMS HTML/파일 업로드로 처리한다.

**Tech Stack:** Python 3.11+, Streamlit, streamlit-quill, httpx SF/PMS, pytest

**Spec:** `docs/superpowers/specs/2026-08-13-tool-first-voc-design.md`

## Global Constraints

- 본문 정책 A: 리치 편집기 = PMS 이슈/댓글 HTML; SF는 제목·요약·필드 (+ 선택적 ContentDocument)
- 기존 Case에 PMS 링크 있으면 **댓글**, 없으면 **이슈 생성** (현행 pipeline과 동일)
- Human Gate(승인) 유지; `dry_run`이면 원격 쓰기 생략·페이로드만
- 1차 라우팅: VOC + SW → PMS (기존과 동일)
- SF 인라인 이미지 본문 비목표; LWC 비목표
- 기존 VOC→PMS 스캔 탭 유지·회귀 없음
- 커밋은 사용자 요청 시에만

## File map

| File | Responsibility |
|------|----------------|
| `src/ai_work_automation/sf/adapter.py` | `create_case`, `create_voc_work_order`, Case 검색 |
| `src/ai_work_automation/tool_first_voc.py` | 오케스트레이션 + 연동 분기 |
| `tests/test_tool_first_voc.py` | 분기·dry_run 단위 테스트 |
| `tests/test_sf_adapter_create.py` (또는 adapter 테스트) | create 호출 형태 |
| `src/ai_work_automation/webui.py` | 「VOC 작성」탭 |
| `docs/local-app.md` | 사용 한 절 |

---

### Task 1: SF Case 검색 + VOC WO / Case create 래퍼

**Files:**
- Modify: `src/ai_work_automation/sf/adapter.py`
- Modify: `src/ai_work_automation/sf/client.py` (필요 시 — `post_sobject` 이미 있음)
- Test: `tests/test_sf_voc_create.py`

**Interfaces:**
- Produces:
  - `find_case_by_number(case_number: str) -> CaseRecord | None` (Id, CaseNumber, Subject, AssetId, activities 등 기존 필드 최대한)
  - `create_case(fields: dict) -> str` (새 Case Id)
  - `create_voc_work_order(*, case_id: str, fields: dict) -> str` (새 WO Id; RecordType VOC, CaseId 필수)
- RecordType / department 필드명은 기존 `wo_department_soql_field` / settings와 맞춤. 필수 최소 셋은 구현 시 org에 맞게 상수화하되, 테스트는 mock client.

- [ ] **Step 1: Failing tests** (mock `client.post_sobject` / `query`)

```python
def test_create_voc_work_order_posts_case_id_and_voc_type(monkeypatch):
    # adapter with fake client capturing body
    # assert body["CaseId"] == "500xx"
    # assert RecordTypeId or RecordType 지정 방식은 구현 선택에 맞게 assert
```

- [ ] **Step 2: Implement minimal create/find on adapter**
- [ ] **Step 3: pytest tests/test_sf_voc_create.py -v** → PASS

참고: `create_technical_service_work_order` 패턴을 복제하되 VOC record type id는 settings 또는 기존 VOC 조회에서 쓰는 DeveloperName `VOC`로 해석 (org에 RecordTypeId 캐시/설정 키가 있으면 재사용).

---

### Task 2: `tool_first_voc` 오케스트레이터

**Files:**
- Create: `src/ai_work_automation/tool_first_voc.py`
- Test: `tests/test_tool_first_voc.py`

**Interfaces:**
- Consumes: SF adapter create/find, `PmsConnector`, `build_pms_draft` / `build_pms_comment`, `_issue_ids_in` (pipeline에서 import 또는 공유 유틸)
- Produces:

```python
@dataclass
class ToolFirstVocInput:
    mode: Literal["new_case", "existing_case"]
    title: str
    department: str  # default "SW"
    pms_html_body: str
    case_number: str | None = None  # existing
    asset_id: str | None = None
    asset_sid: str | None = None
    sf_summary: str = ""  # Case/WO plain summary
    # optional attachment bytes later

@dataclass
class ToolFirstVocResult:
    ok: bool
    dry_run: bool
    case_id: str | None
    work_order_id: str | None
    pms_action: Literal["create", "comment", "skip"] | None
    pms_issue_id: str | None
    pms_url: str | None
    message: str
    links: dict[str, str]  # case/wo/pms urls if any
```

- `run_tool_first_voc(sf, pms, settings, payload: ToolFirstVocInput, *, dry_run: bool, approved: bool) -> ToolFirstVocResult`
  - `approved` False → 쓰지 않고 미리보기 메시지
  - existing: find case → create WO → scan case/WO activities for existing PMS id → comment vs create
  - new: create case → create WO → create PMS issue → append WO activities `PMS – {url}`

- [ ] **Step 1: Tests**
  - existing + issue id present → `add_comment` called, not create
  - existing + no issue → create issue
  - dry_run → no post_sobject / no pms write
- [ ] **Step 2: Implement**
- [ ] **Step 3: pytest PASS**

PMS 이슈 ID 추출은 `pipeline._issue_ids_in` 재사용. Case Activities와 기존 VOC WO Activities를 모두 보도록 한다.

---

### Task 3: Streamlit 「VOC 작성」탭 (메타 + 편집기 + 승인)

**Files:**
- Modify: `src/ai_work_automation/webui.py`

**UI:**
- 탭 추가: `VOC 작성` (스캔 탭 옆 등)
- 모드: `st.radio` 신규 Case / 기존 Case
- 기존: Case 번호 입력 → 조회 버튼 → 제목/Asset/SID caption
- 공통: 제목, 부서, SID/Asset(선택), `st_quill` (또는 기존 리치 에디터) for `pms_html_body`
- 「미리보기」 / 「승인 실행」
- dry_run이면 경고 배지
- 결과: `ToolFirstVocResult` 메시지 + 링크

- [ ] Wire `_sf(s)` + PMS client like `_process_selection`
- [ ] Do not break scan tab
- [ ] Smoke: `py_compile webui.py`

이미지: 1차는 Quill 붙여넣기 + `st.file_uploader`로 파일을 HTML/첨부에 넣는 수준. 전용 크롭 UI는 Task 4.

---

### Task 4: 이미지 크롭·첨부 UX

**Files:**
- Modify: `webui.py` (VOC 작성 섹션)
- Optional small helper: `src/ai_work_automation/media_crop.py` if logic non-trivial

**1차 수용:**
- 클립보드/업로드 이미지를 편집기 또는 미리보기에 넣기
- 간단 크롭: Streamlit 친화 위젯(예: `streamlit-cropper` 또는 canvas) **하나** 선정 후 `pyproject` optional/ui extra에 추가
- 크롭 결과를 PNG/JPEG bytes → base64 `<img>` into PMS HTML 및/또는 SF `create_content_version_from_bytes` + Case/WO link (SF 첨부는 best-effort)

- [ ] Manual checklist in plan report: paste, crop, upload
- [ ] Keep deps optional if heavy; document in local-app.md

---

### Task 5: Docs

**Files:**
- Modify: `docs/local-app.md`, 필요 시 `00-여기부터-읽으세요.md` 한 줄

- [ ] VOC 작성 탭: 신규/기존, PMS 본문, 댓글 규칙 요약
- [ ] Commit only if user asks (with prior tasks)

---

## Spec coverage

| Spec | Task |
|------|------|
| 신규 Case 흐름 | 1–3 |
| 기존 Case + comment/create | 2–3 |
| PMS HTML 편집기 | 3–4 |
| SF 필드 + 선택 첨부 | 1, 4 |
| dry_run / 승인 | 2–3 |
| 스캔 탭 유지 | 3 |
| 문서 | 5 |
