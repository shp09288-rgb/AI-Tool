# VOC→PMS 스캔 — Case 단위 묶기

**날짜:** 2026-08-17  
**상태:** 설계 승인됨 (스펙 리뷰 완료; 구현 계획 있음)  
**대상:** Streamlit 「VOC→PMS」탭 스캔 결과·선택 UI  
**관련:** `scan_candidates` / `ScanRow` (`services.py`), `webui.py` tab_scan, Tool-first VOC(별도 탭)

## 1. 목표

같은 Case에 VOC WO가 여러 개일 때(예: 00183895) **중복처럼 보이는 목록**을 줄이고, 기본 선택 단위를 Case로 바꿔 클릭을 줄인다. 필요할 때만 WO 개별 선택을 유지한다.

성공 기준:

1. 스캔 후 Case 모드에서 동일 Case의 미연동 WO들이 **하나의 선택 항목**으로 보인다.
2. Case를 고르면 그 Case의 **미연동 WO 전부**가 등록 대상이 된다.
3. **WO 개별** 모드로 전환하면 지금처럼 WO 단위로 고를 수 있다.
4. 기존 `_process_selection` / PMS 등록·댓글 규칙은 회귀 없음.

## 2. 비목표 (이번 범위 밖)

- 사이드바 기본 필터를 「미연동만」「내 담당」으로 강제 (후보 B — 차기)
- 필터 프리셋 저장
- SF SOQL을 Case 중심으로 재작성
- Tool-first 「VOC 작성」탭 변경
- 이미 PMS 연동된 WO를 등록 대상에 포함

## 3. 접근 (확정)

| 항목 | 방식 |
|------|------|
| 데이터 | 기존 `scan_candidates` → `list[ScanRow]` 유지 |
| 그룹핑 | 순수 헬퍼로 미연동 행을 Case 키로 묶음 (`group_unlinked_by_case`) |
| UI | Case 단위(기본) / WO 개별 토글 + 선택 → 기존 `_process_selection` |

권장 위치: `services.py`(또는 `scan_grouping.py`)에 그룹 타입·헬퍼, `webui.py`는 표시·토글만.

## 4. 데이터 모델 (헬퍼)

```text
CaseScanGroup:
  case_id: str
  case_number: str
  case_subject: str
  case_owner_name: str
  unlinked: list[ScanRow]   # linked=False only
  linked_count: int         # 같은 case_number의 연동 행 수(표시용, 선택 제외)
```

규칙:

- 그룹 키: `case_id`가 있으면 그것, 없으면 `case_number`
- `unlinked`만 선택·등록에 사용
- 그룹 정렬: Case 번호 또는 그룹 내 최신 `created_date` 기준(구현 시 하나로 고정 — **최신 미연동 WO 생성일 desc**)

## 5. UI

### 5.1 스캔 후 요약

- 기존: `전체 N건 중 PMS 미연동 M건`
- 추가: `미연동 Case G건` (G = 미연동이 1개 이상인 Case 수)

### 5.2 목록 표시

1차:

- **Case 요약 표**(권장): 케이스, 케이스 담당, 미연동 WO 수, (선택) 연동 WO 수, 대표 제목(첫 미연동 또는 최신), 최신 생성일
- 상세 WO 표는 접기/토글 또는 WO 개별 모드에서만 전체 WO 표 유지

구현이 Streamlit에서 부담이면: WO 표를 Case 번호 정렬로 유지하되 **선택 UI만 Case 그룹**해도 성공 기준 1–3을 충족한다. 그 경우에도 Case 요약 caption은 유지.

### 5.3 선택

- 라디오/세그먼트: **`Case 단위`(기본)** / **`WO 개별`**
- Case 단위 multiselect 라벨 예:  
  `{case_number} · 미연동 {k}건 · {title[:40]}`
- 선택 결과 → 각 그룹의 `unlinked`를 flatten → `_process_selection(s, targets, ...)`
- WO 개별: 현행과 동일 (`unlinked` ScanRow multiselect)

PMS 이슈 타입 라디오·미리보기/승인은 기존과 동일.

## 6. 동작 세부

| 상황 | 동작 |
|------|------|
| Case에 미연동 2 + 연동 1 | Case 그룹에 미연동 2만; 요약에 연동 1 표시 가능 |
| Case 모드에서 Case 1개 선택 | targets = 해당 unlinked 전부 |
| WO 모드에서 WO 1개 선택 | targets = 그 1개 |
| 미연동 0 | 기존처럼 “미연동 후보가 없습니다.” |

## 7. 테스트

- `group_unlinked_by_case`: 같은 case_id 두 미연동 → 그룹 1개, unlinked 길이 2
- 연동 행은 `unlinked`에 안 들어가고 `linked_count`에만 반영
- case_id 빈 행은 case_number로 묶임
- (선택) UI는 수동 스모크: Case 모드 라벨 1개 / WO 모드 라벨 2개

## 8. 완료 조건

1. 동일 Case 미연동 2건 → Case 모드 선택 항목 1개  
2. 그 항목 선택 → `_process_selection`에 ScanRow 2개 전달  
3. WO 개별 모드에서 1개만 선택 가능  
4. `tests`로 그룹 헬퍼 커버; 기존 스캔/등록 경로 회귀 없음  

## 9. 열린 결정 (확정)

- 1차 범위 = **Case 묶기 + 선택 모드 C** only  
- 기본 필터(B)·프리셋은 비범위  
- SF 쿼리 변경 없음  
