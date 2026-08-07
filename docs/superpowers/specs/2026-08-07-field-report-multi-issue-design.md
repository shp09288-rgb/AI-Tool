# 출장 보고 멀티 이슈(Case) 자동 분류 설계

**날짜:** 2026-08-07  
**상태:** 구현 완료  
**관련:** `2026-08-07-field-report-unified-ui-design.md`

## 목표

하루 출장에서 Daily Field Service Note에 여러 이슈(Case)를 아래 형식으로 적으면, Tool이 이를 파싱해:

1. 적용 Case 목록을 자동으로 채우고 (UI에서 추가/제외 가능)
2. Case마다 **서로 다른** Case Activity 한 줄을 기록하며
3. Case마다 Technical Service WO를 만들되 **Start/End 시간이 겹치지 않도록** WO별 시간을 지정할 수 있게 한다

예시 형식:

```text
□ 이슈 1 (Case : 00191458)
□ 이슈 2 (Case : 00196633)
□ 이슈 3 (Case : 00197302)
```

## 결정 사항 (합의)

| 항목 | 선택 |
|------|------|
| Case Activity 내용 | **해당 이슈 줄만** (`YYYY-MM-DD [출장자] □ 이슈 N (Case : …)`) |
| 시간 기본값 | 엑셀 L12~L13(없으면 09:00~18:00)을 이슈 개수로 **균등 분할** |
| 시간 겹침 | **경고만** (빨간 안내), 등록은 막지 않음 |
| Case 소스 | 이슈 줄에서 **자동 인식 + UI에서 추가/제외** |
| 첨부 파일 | Case/WO마다 **동일 crop 일자 시트 xlsx** |
| 패턴 없음 | 기존 동작 유지 (T9 Case + B23 단일 요약, 공통 Start/End) |

## 비목표

- 이슈 블록 아래 상세 본문을 Activity에 넣지 않음
- Outlook 메일 HTML 본문 자동화 (별도 스펙)
- Graph/SharePoint 직접 읽기 (로컬 OneDrive 동기화 파일만)

## 파싱 규칙

### 입력 범위

- Daily Field Service Note 본문 셀들을 스캔한다.  
  기본: `B23`부터 crop 마커(`작업 종료 후 근무 형태`) 직전 행까지, 열 B~X.
- 셀 값이 여러 줄이면 줄 단위로도 분리한다.

### 이슈 줄 패턴

정규식(개념):

```text
^[□☐]\s*(.+?)\s*\(\s*Case\s*[:：]\s*(\d{8})\s*\)\s*$
```

- 그룹1: 이슈 라벨 텍스트 (예: `이슈 1`) — Activity에는 줄 전체(□ 포함)를 쓴다.
- 그룹2: 8자리 CaseNumber.
- `Case :` / `Case:` / 전각 콜론 `：` 허용.
- 체크 기호 `□` / `☐` 허용. 없으면 `(Case : ########)` 만으로도 매칭 시도(보조).

### 결과 모델

```text
FieldIssue(
  case_number: str,          # 8자리
  issue_line: str,           # 원문 한 줄 (앞뒤 공백 trim)
  activity_line: str,        # format_activity_line(day, fse, issue_line)
  start: datetime | None,    # 균등 분할 또는 UI 수정
  end: datetime | None,
  included: bool = True,     # UI 제외 토글
)
```

동일 CaseNumber가 두 줄이면 **둘 다 유지**(경고 표시). 등록 시 Case Activity는 줄마다 append, WO는 줄마다 1개(또는 동일 Case면 WO 2개) — **이슈 줄 단위로 WO 1개**.

## UI 변경 (출장 보고 탭)

### Work Order 세부 설정

**공통 (모든 WO 동일)**

- Status (기본 Completed)
- 장비 실태 조사
- Survey 여부

**이슈/WO별 표** (멀티 이슈가 1개 이상일 때)

| 포함 | Case | Activity 미리보기 | Start | End |
|------|------|-------------------|-------|-----|
| ☑ | 00191458 | 2026-08-07 [이동현] □ 이슈 1 … | date+time | date+time |

- 「균등 분할 다시 적용」 버튼: 엑셀 근무 구간으로 Start/End 재계산.
- 겹치는 구간이 있으면 상단에 빨간 경고 목록.
- 기존 Case 멀티셀렉트는 이슈 표와 통합: 표의 포함 체크가 곧 적용 대상.  
  「검색 추가」로 찾은 Case는 **행 추가**. Activity 요약은 기본 `□ (Case : {번호})` 이고, 행마다 한 줄 수정 가능.

**싱글 모드** (이슈 패턴 0개)

- 지금의 T9 기반 Case 선택 + 공통 Start/End + 단일 `fr_sum` Activity 유지.

### 미리보기 / 등록

- dry-run: Case별 Activity, WO Start/End, 첨부 파일명을 표로 표시.
- 실제 등록: 포함된 이슈마다  
  `append_case_activities` → `create_technical_service_work_order`(해당 Start/End) → `attach_file_to_record`(동일 crop xlsx).

## 파이프라인 변경

- `parse_field_issues(workbook, sheet, …) -> list[FieldIssue]`
- `split_workday_slots(start, end, n) -> list[(start, end)]`  
  - 초 단위 균등. 마지막 슬롯 end = 전체 end.
- `run_field_report`가 `list[FieldIssue]`(또는 동등한 per-case payload)를 받아 **이슈 단위 루프**.  
  기존 `case_ids` + 단일 `activity_line` + 단일 `wo_fields` 경로는 싱글 모드용으로 유지하거나 내부에서 이슈 1개로 변환.

## 세세한 UX 버그 (같은 작업에 포함)

자가 점검에서 확인된 항목을 멀티 이슈 작업과 함께 고정한다.

1. **출장자/Activity 세션 고착** — 「시트 불러오기」 시 `fr_fse`/`fr_sum`/시간 위젯을 엑셀 값으로 강제 갱신 (이미 일부 반영, Activity 미리보기가 항상 최신 `fr_fse`를 쓰는지 검증).
2. **미리보기 CoInitialize** — Streamlit 스레드에서 Excel COM 전 `pythoncom.CoInitialize` (반영됨, 회귀 테스트/수동 확인).
3. **End Time `"18:00 PM"` 파싱** — `_as_time` AM/PM 지원 (반영됨).
4. **미리보기 너비 슬라이더** — 유지.

## 성공 기준

- Daily Note에 이슈 3줄이 있으면 UI에 행 3개가 생기고 Case가 자동 선택된다.
- dry-run / 실제 등록 시 Case Activity가 이슈별로 다르다 (A안).
- 기본 Start/End가 겹치지 않게 분할되고, 일부러 겹치면 경고만 보인다.
- 이슈 형식이 없으면 기존 싱글 Case 플로우가 그대로 동작한다.
- 첨부 xlsx에는 하단「작업 종료 후 근무 형태」가 없다.

## 테스트

- `parse_field_issues`: 여러 줄, 전각 콜론, 체크 없음, 패턴 없음.
- `split_workday_slots`: 3등분 경계, n=1.
- `run_field_report` dry-run mock: 이슈 2개 → activity/start/end가 서로 다름.
- 회귀: 기존 `test_field_report_*` 통과.
